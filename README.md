# Abstract-Shape

## Introduction

This repository stores analyses of _abstract shapes_ for [CJKV Unified Ideographs](https://en.wikipedia.org/wiki/CJK_Unified_Ideographs).

The purpose of analyzing abstract shapes is to establish the graphic specification of each character. This is accomplished by analyzing the classes to which the components it contains belong and describing the structure formed by the components.

The graphic specification of components has two sources. The first source is diachronic graphic evolution, which is supported by the systematic changes in Han ideographs. It can be noted that many changes at the writing system level still keep the internal structure of the characters. The second source is language, i.e., the characters containing the component are in the same harmonic scope.

We use prefix expressions composed of components to describe the abstract shape of a character. Each component is either shaped like `[A]` or shaped like `[A(B)]`. The operator is IDC, but define them more abstractly, for example, a character containing three identical components, regardless of how the three components are arranged, we always use `⿲`.

The visualization of this repository is implemented in [another repository](https://github.com/Kushim-Jiang/kushim-jiang.github.io), and [here is the link](https://kushim-jiang.github.io/tools/abstract-shape/).

## Contribute

- Asking

  - Create an [issue](https://github.com/Kushim-Jiang/abstract-shape/issues).
  - Create an [issue](https://github.com/Kushim-Jiang/kushim-jiang.github.io/issues).
  - [Email me.](https://kushim-jiang.github.io/pages/contact/)

- Updating

  1. Clone this repo as the `RepoA`.
  2. Edit the [`RepoA > abstract_shape.xlsx`](input/abstract_shape.xlsx).
  3. Install the required packages in the [`RepoA > requirements.txt`](requirements.txt).
  4. Run Python file [`RepoA > build_txt.py`](src/build_txt.py) to update all the text files.
  5. Pull your request.

- Previewing

  1. Clone [`Kushim-Jiang > kushim-jiang.github.io`](https://github.com/kushim-Jiang/kushim-jiang.github.io) in the same root as the `RepoB`.
  2. Run Python file [`RepoA > build_json.py`](src/build_json.py) to update the JSON file in [`RepoB > assets > abstract.json`](https://github.com/Kushim-Jiang/kushim-jiang.github.io/blob/main/assets/abstract.json).
  3. Run `jekyll s` in the `RepoB` to preview your changes.
