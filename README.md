# **SymbolicAI**
<img src="https://raw.githubusercontent.com/ExtensityAI/symbolicai/main/assets/images/symai_logo.png" width="200px">

### **A Neuro-Symbolic Perspective on Large Language Models (LLMs)**

*Building applications with LLMs at the core using our `Symbolic API` facilitates the integration of classical and differentiable programming in Python.*

Read [**full paper here**](https://arxiv.org/abs/2402.00854).

Read further [**documentation here**](https://symbolicai.readthedocs.io/en/latest/INTRODUCTION.html).

[![PyPI version](https://badge.fury.io/py/symbolicai.svg)](https://badge.fury.io/py/symbolicai) [![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause) [![Twitter](https://img.shields.io/twitter/url/https/twitter.com/dinumariusc.svg?style=social&label=Follow%20%40DinuMariusC)](https://twitter.com/DinuMariusC) [![Twitter](https://img.shields.io/twitter/url/https/twitter.com/symbolicapi.svg?style=social&label=Follow%20%40ExtensityAI)](https://twitter.com/ExtensityAI) [![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/ExtensityAI/symbolicai/issues)
[![Discord](https://img.shields.io/discord/768087161878085643?label=Discord&logo=Discord&logoColor=white)](https://discord.gg/QYMNnh9ra8) [![Hits](https://hits.seeyoufarm.com/api/count/incr/badge.svg?url=https%3A%2F%2Fgithub.com%2FXpitfire%2Fsymbolicai&count_bg=%2379C83D&title_bg=%23555555&icon=&icon_color=%23E7E7E7&title=hits&edge_flat=false)](https://hits.seeyoufarm.com) [![GitHub forks](https://img.shields.io/github/forks/ExtensityAI/symbolicai.svg?style=social&label=Fork&maxAge=2592000)](https://GitHub.com/ExtensityAI/symbolicai) [![GitHub stars](https://img.shields.io/github/stars/ExtensityAI/symbolicai.svg?style=social&label=Star&maxAge=2592000)](https://GitHub.com/ExtensityAI/symbolicai/stargazers/)



<img src="https://raw.githubusercontent.com/ExtensityAI/symbolicai/main/assets/images/preview.gif">

## What is SymbolicAI?

Conceptually, SymbolicAI is a framework that leverages machine learning – specifically LLMs – as its foundation, and composes operations based on task-specific prompting. We adopt a divide-and-conquer approach to break down a complex problem into smaller, more manageable problems. Consequently, each operation addresses a simpler task. By reassembling these operations, we can resolve the complex problem. Moreover, our design principles enable us to transition seamlessly between differentiable and classical programming, allowing us to harness the power of both paradigms.

## Quick Start Guide

This guide will help you get started with SymbolicAI, demonstrating basic usage and key features.

To start, import the library by using:

```python
import symai as ai
```

### Creating and Manipulating Symbols

Our `Symbolic API` is based on object-oriented and compositional design patterns. The `Symbol` class serves as the base class for all functional operations, and in the context of symbolic programming (fully resolved expressions), we refer to it as a terminal symbol. The Symbol class contains helpful operations that can be interpreted as expressions to manipulate its content and evaluate new Symbols `<class 'symai.expressions.Symbol'>`.

```python
# Create a Symbol
sym = ai.Symbol("Welcome to our tutorial.")

# Translate the Symbol
translated = sym.translate('German')
print(translated)  # Output: Willkommen zu unserem Tutorial.
```

### Ranking Objects

Our API can also execute basic data-agnostic operations like `filter`, `rank`, or `extract` patterns. For instance, we can rank a list of numbers:

```python
# Ranking objects
import numpy as np
sym = ai.Symbol(np.array([1, 2, 3, 4, 5, 6, 7]))
ranked = sym.rank(measure='numerical', order='descending')
print(ranked)  # Output: ['7', '6', '5', '4', '3', '2', '1']
```

### Evaluating Expressions

Evaluations are resolved in the language domain and by best effort. We showcase this on the example of [word2vec](https://arxiv.org/abs/1301.3781).

**Word2Vec** generates dense vector representations of words by training a shallow neural network to predict a word based on its neighbors in a text corpus. These resulting vectors are then employed in numerous natural language processing applications, such as sentiment analysis, text classification, and clustering.

In the example below, we can observe how operations on word embeddings (colored boxes) are performed. Words are tokenized and mapped to a vector space where semantic operations can be executed using vector arithmetic.

<img src="https://raw.githubusercontent.com/ExtensityAI/symbolicai/main/assets/images/img3.png" width="450px">

Similar to word2vec, we aim to perform contextualized operations on different symbols. However, as opposed to operating in vector space, we work in the natural language domain. This provides us the ability to perform arithmetic on words, sentences, paragraphs, etc., and verify the results in a human-readable format.

The following examples display how to evaluate such an expression using a string representation:

```python
# Word analogy
result = ai.Symbol('King - Man + Women').expression()
print(result)  # Output: Queen
```

#### Dynamic Casting

We can also subtract sentences from one another, where our operations condition the neural computation engine to evaluate the Symbols by their best effort. In the subsequent example, it identifies that the word `enemy` is present in the sentence, so it deletes it and replaces it with the word `friend` (which is added):

```python
# Sentence manipulation
result = ai.Symbol('Hello my enemy') - 'enemy' + 'friend'
print(result)  # Output: Hello my friend
```

Additionally, the API performs dynamic casting when data types are combined with a Symbol object. If an overloaded operation of the Symbol class is employed, the Symbol class can automatically cast the second object to a Symbol. This is a convenient way to perform operations between `Symbol` objects and other data types, such as strings, integers, floats, lists, etc., without cluttering the syntax.

#### Probabilistic Programming

In this example, we perform a fuzzy comparison between two numerical objects. The `Symbol` variant is an approximation of `numpy.pi`. Despite the approximation, the fuzzy equals `==` operation still successfully compares the two values and returns `True`.

```python
# Fuzzy comparison
sym = ai.Symbol('3.1415...')
print(sym == numpy.pi)  # Output: True
```

### 🧠 Causal Reasoning

The main goal of our framework is to enable reasoning capabilities on top of the statistical inference of Language Models (LMs). As a result, our `Symbol` objects offers operations to perform deductive reasoning expressions. One such operation involves defining rules that describe the causal relationship between symbols. The following example demonstrates how the `&` operator is overloaded to compute the logical implication of two symbols.

```python
result = ai.Symbol('The horn only sounds on Sundays.') & ai.Symbol('I hear the horn.')
print(result)  # Output: It is Sunday.
```

The current `&` operation overloads the `and` logical operator and sends `few-shot` prompts to the neural computation engine for statement evaluation. However, we can define more sophisticated logical operators for `and`, `or`, and `xor` using formal proof statements. Additionally, the neural engines can parse data structures prior to expression evaluation. Users can also define custom operations for more complex and robust logical operations, including constraints to validate outcomes and ensure desired behavior.

### 🪜 Next Steps

This quick start guide covers the basics of SymbolicAI. We also provide an interactive [notebook](https://github.com/ExtensityAI/symbolicai/blob/main/notebooks/Basics.ipynb) that reiterates these basics. For more detailed information and advanced usage explore the topics and tutorials listed below.

* More in-depth guides: {doc}`Tutorials <TUTORIALS/index>`
* Using different neuro-symbolic engines: {doc}`Engines <ENGINES/index>`
* Advanced causal reasoning: {doc}`Causal Reasoning <FEATURES/causal_reasoning>`
* Using operations to customize and define api behavior: {doc}`Operations <FEATURES/operations>`
* Using expressions to create complex behaviors: {doc}`Expressions <FEATURES/expressions>`
* Managing modules and imports: {doc}`Import Class <FEATURES/import>`
* Error handling and debugging: {doc}`Error Handling and Debugging <FEATURES/error_handling>`
* Built-in tools: {doc}`Tools <TOOLS/index>`

### Acknowledgements

We have a long list of acknowledgements. Special thanks go to our colleagues and friends at the [Institute for Machine Learning at Johannes Kepler University (JKU), Linz](https://www.jku.at/institut-fuer-machine-learning/) for their exceptional support and feedback. We are also grateful to the [AI Austria RL Community](https://aiaustria.com/rl-community) for supporting this project. Additionally, we appreciate all contributors to this project, regardless of whether they provided feedback, bug reports, code, or simply used the framework. Your support is highly valued.

Finally, we would like to thank the open-source community for making their APIs and tools publicly available, including (but not limited to) [PyTorch](https://pytorch.org/), [Hugging Face](https://huggingface.co/), [OpenAI](https://openai.com/), [GitHub](https://github.com/), [Microsoft Research](https://www.microsoft.com/en-us/research/), and many others.

Special thanks are owed to [Kajetan Schweighofer](https://www.linkedin.com/in/kajetan-schweighofer-a61113202/?originalSubdomain=at), [Markus Hofmarcher](https://www.linkedin.com/in/markus-hofmarcher-2722141b8/?originalSubdomain=at), [Thomas Natschläger](https://www.linkedin.com/in/thomas-natschlaeger/?originalSubdomain=at), and [Sepp Hochreiter](https://scholar.google.at/citations?user=tvUH3WMAAAAJ&hl=en).

### Contribution

If you wish to contribute to this project, please refer to [the docs](https://symbolicai.readthedocs.io/en/latest/CONTRIBUTING.html) for details on our code of conduct, as well as the process for submitting pull requests. Any contributions are greatly appreciated.

### 📜 Citation

```bibtex
@software{Dinu_SymbolicAI_2022,
  author = {Dinu, Marius-Constantin},
  editor = {Leoveanu-Condrei, Claudiu},
  title = {{SymbolicAI: A Neuro-Symbolic Perspective on Large Language Models (LLMs)}},
  url = {https://github.com/ExtensityAI/symbolicai},
  month = {11},
  year = {2022}
}
```

### 📝 License

This project is licensed under the BSD-3-Clause License - refer to [the docs](https://symbolicai.readthedocs.io/en/latest/LICENSE.html).

### Like this Project?

If you appreciate this project, please leave a star ⭐️ and share it with friends and colleagues. To support the ongoing development of this project even further, consider donating. Thank you!

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/donate/?hosted_button_id=WCWP5D2QWZXFQ)

We are also seeking contributors or investors to help grow and support this project. If you are interested, please reach out to us.

### 📫 Contact

Feel free to contact us with any questions about this project via [email](mailto:office@extensity.ai), through our [website](https://extensity.ai/), or find us on Discord:

[![Discord](https://img.shields.io/discord/768087161878085643?label=Discord&logo=Discord&logoColor=white)](https://discord.gg/QYMNnh9ra8)

To contact me directly, you can find me on [LinkedIn](https://www.linkedin.com/in/mariusconstantindinu/), [Twitter](https://twitter.com/DinuMariusC), or at my personal [website](https://www.dinu.at/).
