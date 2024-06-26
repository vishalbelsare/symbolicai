import unittest
from pathlib import Path

from symai import Symbol, Expression
from symai.core_ext import bind


class TestOpenAIEngine(unittest.TestCase):
    def test_init(self):
        x = Symbol('This is a test!')
        x.query('What is this?')

        # if no errors are raised, then the test is successful
        self.assertTrue(True)

    def test_vision(self):
        file = Path(__file__).parent.parent / 'assets' / 'images' / 'cat.jpg'
        x = Symbol(f'<<vision:{file}:>>')
        res = x.query('What is in the image?')

        # it makes sense here to explicitly check if there is a cat; we are testing the vision component
        # which only gpt-4-* models can handle and they should be able to detect a cat in the image
        self.assertTrue('cat' in res.value)

        file = 'https://raw.githubusercontent.com/ExtensityAI/symbolicai/main/assets/images/cat.jpg'
        x = Symbol(f'<<vision:{file}:>>')
        res = x.query('What is in the image?')

        # same check but for url
        self.assertTrue('cat' in res.value)

    def test_tokenizer(self):
        messages = [
            {
                "role": "system",
                "content": "You are a helpful, pattern-following assistant that translates corporate jargon into plain English.",
            },
            {
                "role": "system",
                "name": "example_user",
                "content": "New synergies will help drive top-line growth.",
            },
            {
                "role": "system",
                "name": "example_assistant",
                "content": "Things working well together will increase revenue.",
            },
            {
                "role": "system",
                "name": "example_user",
                "content": "Let's circle back when we have more bandwidth to touch base on opportunities for increased leverage.",
            },
            {
                "role": "system",
                "name": "example_assistant",
                "content": "Let's talk later when we're less busy about how to do better.",
            },
            {
                "role": "user",
                "content": "This late pivot means we don't have time to boil the ocean for the client deliverable.",
            },
        ]

        response = Expression.prompt(messages, raw_output=True)
        api_tokens = response.usage.prompt_tokens
        tik_tokens = self._compute_required_tokens(messages)

        self.assertEqual(api_tokens, tik_tokens)

    @bind(engine='neurosymbolic', property='compute_required_tokens')(lambda: 0)
    def _compute_required_tokens(self): pass


if __name__ == '__main__':
    unittest.main()
