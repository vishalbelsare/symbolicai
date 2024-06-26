import asyncio
import json
import logging
import re
from typing import List, Optional

import aiohttp

from ....utils import CustomUserWarning
from ...base import Engine
from ...settings import SYMAI_CONFIG

logging.getLogger("requests").setLevel(logging.ERROR)
logging.getLogger("urllib").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.ERROR)

class LlamaCppTokenizer:
    _server_endpoint = SYMAI_CONFIG.get('NEUROSYMBOLIC_ENGINE_API_KEY')

    @staticmethod
    async def _arequest_encode(text: str) -> List[int]:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{LlamaCppTokenizer._server_endpoint}/extras/tokenize", json={"input": text}) as res:
                if res.status != 200:
                    raise ValueError(f"Request failed with status code: {res.status}")
                res_json = await res.json()
                return res_json['tokens']

    @staticmethod
    async def _areqest_decode(tokens: List[int]) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{LlamaCppTokenizer._server_endpoint}/extras/detokenize", json={"tokens": tokens}) as res:
                if res.status != 200:
                    raise ValueError(f"Request failed with status code: {res.status}")
                res_json = await res.json()
                return res_json['text']

    @staticmethod
    def encode(text: str) -> List[int]:
        return asyncio.run(LlamaCppTokenizer._arequest_encode(text))

    @staticmethod
    def decode(tokens: List[int]) -> str:
        return asyncio.run(LlamaCppTokenizer._areqest_decode(tokens))

class LlamaCppEngine(Engine):
    def __init__(self):
        super().__init__()
        self.config = SYMAI_CONFIG
        self.server_endpoint = self.config.get('NEUROSYMBOLIC_ENGINE_API_KEY')
        if (self.server_endpoint is None or self.server_endpoint == '') and \
            not self.server_endpoint.startswith('http:'):
            raise ValueError('Invalid server endpoint! You are using the llama.cpp engine, but the server endpoint is not set. Please add the `NEUROSYMBOLIC_ENGINE_API_KEY` in the format `http://<ip>:<port>` to the `symai.config.json` file.')
        self.tokenizer = LlamaCppTokenizer # backwards compatibility with how we handle tokenization, i.e. self.tokenizer().encode(...)

    def id(self) -> str:
        if self.config.get('NEUROSYMBOLIC_ENGINE_MODEL') and self.config.get('NEUROSYMBOLIC_ENGINE_MODEL') == 'llama.cpp':
            return 'neurosymbolic'
        return super().id() # default to unregistered

    def command(self, *args, **kwargs):
        super().command(*args, **kwargs)
        if 'NEUROSYMBOLIC_ENGINE_MODEL' in kwargs:
            self.model = kwargs['NEUROSYMBOLIC_ENGINE_MODEL']
        if 'seed' in kwargs:
            self.seed = kwargs['seed']
        if 'except_remedy' in kwargs:
            self.except_remedy = kwargs['except_remedy']

    def compute_required_tokens(self, messages) -> int:
        #@TODO: quite non-trivial how to handle this with the llama.cpp server
        raise NotImplementedError

    def compute_remaining_tokens(self, prompts: list) -> int:
        #@TODO: quite non-trivial how to handle this with the llama.cpp server
        raise NotImplementedError

    async def arequest(self, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.server_endpoint}/v1/chat/completions", json=kwargs) as res:
                if res.status != 200:
                    raise ValueError(f"Request failed with status code: {res.status}")
                res_json = await res.json()
                return res_json

    def forward(self, argument):
        kwargs = argument.kwargs
        prompts_ = argument.prop.prepared_input

        stop = kwargs.get('stop')
        seed = kwargs.get('seed')
        temperature = kwargs.get('temperature', 0.6)
        frequency_penalty = kwargs.get('frequency_penalty', 0)
        presence_penalty = kwargs.get('presence_penalty', 0)
        top_p = kwargs.get('top_p', 0.95)
        min_p = kwargs.get('min_p', 0.05)
        n = kwargs.get('n', 1)
        max_tokens = kwargs.get('max_tokens')
        top_logprobs = kwargs.get('top_logprobs')
        top_k = kwargs.get('top_k', 40)
        repeat_penalty = kwargs.get('repeat_penalty', 1)
        logits_bias = kwargs.get('logits_bias')
        logprobs = kwargs.get('logprobs', False)
        functions = kwargs.get('functions')
        function_call = kwargs.get('function_call')
        grammar = kwargs.get('grammar')
        except_remedy = kwargs.get('except_remedy') #@TODO: mimic openai logic here (somehow)

        try:
            res = asyncio.run(
                    self.arequest(
                        messages=prompts_,
                        temperature=temperature,
                        frequency_penalty=frequency_penalty,
                        presence_penalty=presence_penalty,
                        top_p=top_p,
                        stop=stop,
                        seed=seed,
                        max_tokens=max_tokens,
                        top_k=top_k,
                        repeat_penalty=repeat_penalty,
                        logits_bias=logits_bias,
                        logprobs=logprobs,
                        top_logprobs=top_logprobs,
                        functions=functions,
                        function_call=function_call,
                        grammar=grammar,
                        n=n,
                    )
                )

        except Exception as e:
            if except_remedy is not None:
                res = except_remedy(self, e, callback, argument)
            else:
                raise e

        metadata = {'raw_output': res}

        rsp    = [r['message']['content'] for r in res['choices']]
        output = rsp if isinstance(prompts_, list) else rsp[0]
        return output, metadata

    def prepare(self, argument):
        if argument.prop.raw_input:
            if not argument.prop.processed_input:
                raise ValueError('Need to provide a prompt instruction to the engine if raw_input is enabled.')
            value = argument.prop.processed_input
            if type(value) != list:
                if type(value) != dict:
                    value = {'role': 'user', 'content': str(value)}
                value = [value]
            argument.prop.prepared_input = value
            return

        _non_verbose_output = """<META_INSTRUCTION/>\n You will NOT output verbose preambles or post explanation, such as "Sure, let me...", "Hope that was helpful...", "Yes, I can help you with that...", etc. You will consider well formatted output, e.g. for sentences you will use punctuation, spaces, etc. or for code indentation, etc.\n"""

        #@TODO: Non-trivial how to handle user/system/assistant roles;
        #       For instance Mixtral-8x7B can't use the system role with llama.cpp while other models can, or Mixtral-8x22B expects the conversation roles must
        #       alternate user/assistant/user/assistant/..., so how to handle this?
        #       For now just use the user, as one can rephrase the system from the user perspective.
        user: str = ""

        if argument.prop.suppress_verbose_output:
            user += _non_verbose_output
        user = f'{user}\n' if user and len(user) > 0 else ''

        ref = argument.prop.instance
        static_ctxt, dyn_ctxt = ref.global_context
        if len(static_ctxt) > 0:
            user += f"<STATIC_CONTEXT/>\n{static_ctxt}\n\n"

        if len(dyn_ctxt) > 0:
            user += f"<DYNAMIC_CONTEXT/>\n{dyn_ctxt}\n\n"

        payload = argument.prop.payload
        if argument.prop.payload:
            user += f"<ADDITIONAL_CONTEXT/>\n{str(payload)}\n\n"

        examples: List[str] = argument.prop.examples
        if examples and len(examples) > 0:
            user += f"<EXAMPLES/>\n{str(examples)}\n\n"

        if argument.prop.prompt is not None and len(argument.prop.prompt) > 0:
            user += f"<INSTRUCTION/>\n{str(argument.prop.prompt)}\n\n"

        if argument.prop.template_suffix:
            user += f" You will only generate content for the placeholder `{str(argument.prop.template_suffix)}` following the instructions and the provided context information.\n\n"

        user += str(argument.prop.processed_input)

        argument.prop.prepared_input = [
            {"role": "user", "content": user},
        ]

