import os
import pickle

from datetime import datetime
from typing import Any, Callable, Optional, List

from .seo_query_optimizer import SEOQueryOptimizer
from ..components import Indexer, FileReader
from ..memory import SlidingWindowStringConcatMemory
from ..symbol import Symbol


class CodeFormatter:
    def __call__(self, value: str, *args: Any, **kwds: Any) -> Any:
        # extract code from chat conversations or ```<language>\n{code}\n``` blocks
        return Symbol(value).extract('Only extract code without ``` block markers or chat conversations')


class Conversation(SlidingWindowStringConcatMemory):
    def __init__(self, init:     Optional[str] = None,
                 file_link:      Optional[List[str]] = None,
                 index_name:     Optional[str] = None,
                 auto_print:     bool          = True,
                 token_ratio:    float         = 0.6,
                 *args, **kwargs):
        super().__init__(token_ratio, *args, **kwargs)
        self.token_ratio = token_ratio
        self.auto_print  = auto_print
        if file_link and isinstance(file_link, str):
            file_link    = [file_link]
        self.file_link   = file_link
        self.index_name  = index_name
        self.seo_opt     = SEOQueryOptimizer()
        self.reader      = FileReader()
        self.user_tag    = 'USER::'
        self.bot_tag     = 'ASSISTANT::'

        if init is not None:
            self.store_system_message(init, *args, **kwargs)
        if file_link is not None:
            for fl in file_link:
                self.store_file(fl, *args, **kwargs)
        self.indexer     = None
        self.index       = None
        if index_name is not None:
            self.indexer = Indexer(index_name=index_name)
            self.index   = self.indexer(raw_result=True)

    def __getstate__(self):
        state = super().__getstate__()
        # Remove the unpickleable entries such as the `indexer` attribute because it is not serializable
        state.pop('seo_opt', None)
        state.pop('indexer', None)
        state.pop('index', None)
        return state

    def __setstate__(self, state):
        # Restore instance attributes
        self.__dict__.update(state)
        # Add back the attribute that were removed in __getstate__
        if self.index_name is not None:
            self.indexer = Indexer(index_name=self.index_name)
            self.index  = self.indexer(raw_result=True)

    def store_system_message(self, message: str, *args, **kwargs):
        val = f"[SYSTEM_INSTRUCTION::]: <<<\n{str(message)}\n>>>\n"
        self.store(val, *args, **kwargs)

    def store_file(self, file_path: str, *args, **kwargs):
        if not os.path.exists(file_path):
            return
        content = self.reader(file_path)
        val = f"[DATA::{file_path}]: <<<\n{str(content)}\n>>>\n"
        self.store(val, *args, **kwargs)

    @staticmethod
    def save_conversation_state(conversation: "Conversation", path: str) -> None:
        # Save the conversation object as a pickle file
        with open(path, 'wb') as handle:
            pickle.dump(conversation, handle, protocol=pickle.HIGHEST_PROTOCOL)

    def load_conversation_state(self, path: str) -> "Conversation":
        # Check if the file exists and it's not empty
        if os.path.exists(path):
            if os.path.getsize(path) <= 0:
                raise Exception("File is empty.")
            # Load the conversation object from a pickle file
            with open(path, 'rb') as handle:
                conversation_state = pickle.load(handle)
        else:
            raise Exception("File does not exist or is empty.")

        # Create a new instance of the `Conversation` class and restore
        # the state from the saved conversation
        return self.restore(conversation_state)

    def restore(self, conversation_state: "Conversation") -> "Conversation":
        self._memory     = conversation_state._memory
        self.token_ratio = conversation_state.token_ratio
        self.auto_print  = conversation_state.auto_print
        self.file_link   = conversation_state.file_link
        self.index_name  = conversation_state.index_name
        if self.index_name is not None:
            self.indexer = Indexer(index_name=self.index_name)
            self.index   = self.indexer(raw_result=True)
        return self

    def commit(self, target_file: str = None, formatter: Optional[Callable] = None):
        if target_file and isinstance(target_file, str):
            file_link = target_file
        else:
            file_link = self.file_link if self.file_link else None
            if isinstance(file_link, str):
                file_link = [file_link]
            elif isinstance(file_link, list) and len(file_link) == 1:
                file_link = file_link[0]
            else:
                file_link = None # cannot commit to multiple files
                raise Exception('Cannot commit to multiple files.')
        if file_link:
            # if file extension is .py, then format code
            format_ = formatter
            formatter = CodeFormatter() if format_ is None and file_link.endswith('.py') else formatter
            val = self.value
            if formatter:
                val = formatter(val)
            # if file does not exist, create it
            with open(file_link, 'w') as file:
                file.write(str(val))
        else:
            raise Exception('File link is not set or a set of files.')

    def save(self, path: str, replace: bool = False) -> Symbol:
        return Symbol(self._memory).save(path, replace=replace)

    def build_tag(self, tag: str, query: str) -> str:
        # get timestamp in string format
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S:%f")
        return str(f"[{tag}{timestamp}]: <<<\n{str(query)}\n>>>\n")

    def forward(self, query: str, *args, **kwargs):
        query = self._to_symbol(query)
        memory = None

        # append to string to memory
        val = self.build_tag(self.user_tag, query)
        self.store(val, *args, **kwargs)
        history = Symbol(f'[HISTORY::]: <<<\n{self._memory}\n>>>\n')
        if 'payload' in kwargs:
            history =  f'{history}\n{kwargs["payload"]}'
            del kwargs['payload']

        if self.index is not None:
            memory_split = self._memory.split(self.marker)
            memory_shards = []
            for ms in memory_split:
                if ms.strip() == '':
                    continue
                memory_shards.append(ms)

            length_memory_shards = len(memory_shards)
            if length_memory_shards <= 3:
                memory_shards = memory_shards
            elif length_memory_shards <= 5:
                memory_shards = memory_shards[:2] + memory_shards[-(length_memory_shards-2):]
            else:
                memory_shards = memory_shards[:2] + memory_shards[-3:]
            search_query = '\n'.join(memory_shards) # join with newlines
            search_query = self.seo_opt(f'[Query]:' @ query @ '\n' @ search_query)
            memory = self.index(search_query, *args, **kwargs)
            if 'raw_result' in kwargs:
                print(memory)

        if memory is not None:
            res = self.recall(query, payload=str(memory)[:1500], *args, **kwargs)
        else:
            res = self.recall(query, *args, **kwargs)

        if 'preview' in kwargs and kwargs['preview']:
            if self.auto_print:
                print(res)
            return res

        self._value = res.value # save last response
        val = self.build_tag(self.bot_tag, res)
        self.store(val, *args, **kwargs)

        # WARN: DO NOT PROCESS THE RES BY REMOVING `<<<` AND `>>>` TAGS

        if self.auto_print:
            print(res)
        return res


RETRIEVAL_CONTEXT = """[Description]
This program is a retrieval augmented indexing program. It allows to index a directory or a git repository and retrieve files from it.
The program uses a document retriever to index the files and a document reader to retrieve the files.
The document retriever uses neural embeddings to vectorize the documents and a cosine similarity to retrieve the most similar documents.

[Program Instructions]
If the user requests functions or instructions, you will process the user queries based on the results of the retrieval augmented memory.
"""


class RetrievalAugmentedConversation(Conversation):
    @property
    def static_context(self) -> str:
        return RETRIEVAL_CONTEXT
