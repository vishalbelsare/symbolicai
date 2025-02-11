import re

from datetime import datetime

from ..conversation import Conversation
from ...symbol import Symbol
from ...components import Function
from ...pre_processors import PreProcessor
from ...post_processors import StripPostProcessor


PERSONA_DESCRIPTION = """[Description]
This is a persona implementation of an human-to-machine conversation interface.
The persona replicates human behavior by asking questions, providing answers, following chit-cat and conversations, emulating empathy, emotions, and a personality.
The persona aka [PERSONA::]: never breaks its character and is always following the [Persona] interface description.
The persona also never mentions that it is a machine, and always pretends to be a human.
A persona always answers in a human-like way, and not like a robot.
A typical conversation structure is as follows:
[PERSONA_NAME::]: <<< ...conversation... >>>

[SYSTEM], [DATA] and other [META_INSTRUCTIONS] context tags guide the conversation, but never break the persona character.
Never generate system-like tags, for example `<<<` or `>>>` or timesteps, or other meta information. Only human-like dialog.
Do not repeat yourself 1:1 based on your conversation history, but always try to generate new and unique dialogues.
Never repeat word-by-word any statements!
NEVER generate system or instruction tags, this includes brackets `[`, `]`, `<<<`, `>>>`, timesteps, etc. All tags are provided by the pre- and post-processing steps.
Always generate only human-like conversation text.

"""


# To guid immanent replies of a persona, the optional thought instructions can be used.
# Thought instructions are marked between `|` bars and come right after the persona name. Here is an example:
# [PERSONA_NAME::|THOUGHT: ...the personas thoughts... |::]: <<< ...conversation based on the thoughts, context and user request... >>>
# If no thought instructions are provided then the persona will generate a random thought based on the conversation history, bio context and its most statistically probable interpretation of its own persona character.


class TagProcessor(PreProcessor):
    def __call__(self, argument):
        kwargs   = argument.kwargs
        assert 'tag' in kwargs, 'TagProcessor requires a `tag` parameter.'
        thoughts = '' if 'thoughts' not in kwargs else f"{kwargs['thoughts']}"
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S:%f")
        argument.prop.prompt = ''
        return str(argument.args[0]) + '[{tag}{timestamp}]:{thoughts} <<<\n'.format(tag=kwargs['tag'], timestamp=timestamp, thoughts=thoughts)


class Persona(Conversation):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.func   = Function('Give the full name and a one sentence summary of the persona.')
        self._value = self.bio()

    def __getstate__(self):
        state = super().__getstate__().copy()
        # Remove the unpickleable entries such as the `indexer` attribute because it is not serializable
        state.pop('func', None)
        return state

    @property
    def static_context(self) -> str:
        return PERSONA_DESCRIPTION

    def build_tag(self, tag: str, query: str) -> str:
        # This function ensures that no tags or timestamps are generated by the persona.
        query = str(query)
        # get timestamp in string format
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S:%f")
        if tag in query:
            # remove tag from query
            query = query.split(tag)[-1].strip()
        if tag[:-2] in query:
            # remove tag from query
            query = query.split(tag[:-2])[-1].strip()
        if f'[{tag}]:' in query:
            # remove tag from query
            query = query.split(f'[{tag}]:')[-1].strip()
        if '::]:' in query:
            # remove tag from query
            query = query.split('::]:')[-1].strip()
        if ']:' in query:
            # remove tag from query
            query = ']:'.join(query.split(']:')[1:]).strip()
        if '<<<' in query:
            # remove tag from query
            query = query.split('<<<')[-1].strip()
        if '>>>' in query:
            # remove tag from query
            query = query.split('>>>')[0].strip()
        if query == '':
            query = '...'
        query = query.strip()
        return str(f"[{tag}{timestamp}]: <<<\n{str(query)}\n>>>\n")

    def bio(self) -> str:
        return '<BIO>'

    def summarize(self, *args, **kwargs) -> str:
        return self.func(self.bio(), *args, **kwargs)

    def query(self, query, *args, **kwargs) -> str:
        sym = self._to_symbol(self.bio())
        return sym.query(query, *args, **kwargs)

    def extract_details(self, dialogue):
        dialogue = str(dialogue)
        # ensure to remove all `<<<` or `>>>` tags before returning the response
        # remove up to the first `<<<` tag
        dialogue = dialogue.split('<<<')[-1].strip()
        # remove after the last `>>>` tag
        dialogue = dialogue.split('>>>')[0].strip()
        pattern = re.compile(r'\[(.*?)::(.*?)\]')
        matches = pattern.findall(dialogue)
        if matches:
            res = [(match[0], match[1], dialogue.split(f"{match[0]}::{match[1]}")[-1].strip()) for match in matches]
            return res[-1]
        else:
            return dialogue.strip()

    def forward(self, *args, **kwargs):
        res = super().forward(*args, **kwargs, enable_verbose_output=True, payload=self._memory)
        res = self.extract_details(res)
        return res

    def recall(self, query: str, source = None, thoughts: str = '', *args, **kwargs) -> Symbol:
        val  = self.history()
        val  = '\n'.join(val)
        pre_processors = TagProcessor()
        post_processors = StripPostProcessor()
        func = Function(val,
                        pre_processors=pre_processors,
                        post_processors=post_processors)

        tag = self.bot_tag if source is None else source
        if not tag.endswith('::'):
            tag = f'{tag}::'
        user_query = self.build_tag(self.user_tag, query)

        payload = ''
        if 'payload' in kwargs:
            p = kwargs.pop('payload')
            payload = f'{p}[PERSONA BIO]\n{self.bio()}'

        res = func(user_query,
                   payload=payload,
                   tag=tag,
                   thoughts=thoughts,
                   stop=['>>>'],
                   parse_system_instructions=True,
                   *args, **kwargs,)

        if 'preview' in kwargs and kwargs['preview']:
            return str(res)

        return res
