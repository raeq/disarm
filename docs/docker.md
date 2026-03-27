# Docker

translit provides an official Docker image so you can use it without installing Python or any packages on your machine. The image is small (~50–60 MB), runs as a non-root user, and works on both Intel/AMD and ARM machines (including Apple Silicon and AWS Graviton).

## Prerequisites

You need Docker installed on your machine. If you don't have it yet:

- **macOS**: [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/)
- **Windows**: [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
- **Linux**: [Docker Engine](https://docs.docker.com/engine/install/)

To check that Docker is working, open a terminal and run:

```bash
docker --version
```

You should see something like `Docker version 27.x.x`. If you get "command not found", Docker isn't installed yet.

## Pulling the image

The image is published to GitHub Container Registry. Pull it with:

```bash
docker pull ghcr.io/raeq/translit:latest
```

You can also pin to a specific version:

```bash
docker pull ghcr.io/raeq/translit:0.1.15
```

## Quick start

Once pulled, you can run commands immediately:

```bash
docker run ghcr.io/raeq/translit transliterate "café résumé"
```

Output:

```
cafe resume
```

For convenience, you can create a shell alias so you don't have to type the full image name every time:

```bash
alias translit='docker run --rm -i ghcr.io/raeq/translit'
```

Now you can just type:

```bash
translit slugify "Hello World!"
```

!!! tip
    Add the alias line to your `~/.bashrc`, `~/.zshrc`, or shell profile so it persists across terminal sessions.

## Commands

The image provides five subcommands. Each one accepts input as an argument or piped from stdin.

### transliterate

Convert Unicode text to ASCII:

```bash
docker run ghcr.io/raeq/translit transliterate "Москва"
```

Output: `Moskva`

Use `--lang` for language-specific transliteration:

```bash
docker run ghcr.io/raeq/translit transliterate --lang de "Ärger"
```

Output: `Aerger` (German convention: ä → ae)

More examples:

```bash
# Chinese (Hanzi → Pinyin)
docker run ghcr.io/raeq/translit transliterate "北京市"
# → bei jing shi

# Korean (Hangul → Revised Romanization)
docker run ghcr.io/raeq/translit transliterate "서울"
# → seo ul

# Japanese (Kana → Hepburn)
docker run ghcr.io/raeq/translit transliterate "ひらがな"
# → hiragana
```

### slugify

Generate URL-safe slugs:

```bash
docker run ghcr.io/raeq/translit slugify "Hello, World!"
```

Output: `hello-world`

Options:

```bash
# Custom separator
docker run ghcr.io/raeq/translit slugify --separator "_" "Hello World"
# → hello_world

# Maximum length
docker run ghcr.io/raeq/translit slugify --max-length 10 "A very long title for a blog post"
# → a-very-lon
```

### normalize

Apply Unicode normalization:

```bash
docker run ghcr.io/raeq/translit normalize "café"
```

Output: `café` (NFC by default — composed form)

Use `--form` to choose the normalization form:

```bash
# NFKC decomposes ligatures and compatibility characters
docker run ghcr.io/raeq/translit normalize --form NFKC "ﬁ"
# → fi

# NFD decomposes to base character + combining marks
docker run ghcr.io/raeq/translit normalize --form NFD "é"
# → é (now two codepoints: e + combining acute accent)
```

The four available forms are `NFC`, `NFD`, `NFKC`, and `NFKD`.

### demojize

Expand emoji to their text descriptions:

```bash
docker run ghcr.io/raeq/translit demojize "Hello 😀 World 🌍"
```

Output: `Hello grinning face World globe showing Europe-Africa`

### pipeline

Run multiple processing steps in a single pass. Steps are provided as a comma-separated list:

```bash
docker run ghcr.io/raeq/translit pipeline --steps "normalize,fold_case,transliterate" "Héllo WÖRLD"
```

Output: `hello world`

Available steps: `normalize`, `transliterate`, `fold_case`, `collapse_whitespace`, `strip_accents`, `confusables`, `strip_control`, `strip_zero_width`, `demojize`.

When using the `normalize` step, you can specify the form with `--form`:

```bash
docker run ghcr.io/raeq/translit pipeline --steps "normalize,fold_case" --form NFKC "ﬁLTER"
# → filter
```

## Piping input from stdin

All commands accept piped input, which is useful for processing files or chaining with other tools:

```bash
# Process a file
cat myfile.txt | docker run -i ghcr.io/raeq/translit slugify

# Chain with other commands
echo "Ünïcödé Tëxt" | docker run -i ghcr.io/raeq/translit transliterate
# → Unicode Text

# Process output from another program
curl -s https://example.com/title | docker run -i ghcr.io/raeq/translit slugify
```

!!! note
    When piping input, use `docker run -i` (the `-i` flag keeps stdin open).

## Using as a base image

You can use the translit image as a base for your own Docker images. The full Python `translit` package is available for import:

```dockerfile
FROM ghcr.io/raeq/translit:latest

# Switch to root to install additional packages
USER root
RUN pip install --no-cache-dir flask
USER translit

COPY app.py /app/app.py
WORKDIR /app
ENTRYPOINT ["python", "app.py"]
```

In your `app.py`:

```python
from translit import slugify, transliterate, TextPipeline

pipe = TextPipeline(normalize="NFKC", fold_case=True, transliterate=True)
print(pipe("Héllo Wörld"))  # → "hello world"
```

## Building the image locally

If you want to build the image yourself (e.g., to test changes to the CLI):

```bash
git clone https://github.com/raeq/translit.git
cd translit
docker build -t translit-rs .
```

Then run with your local image name:

```bash
docker run translit-rs slugify "Hello World"
```

!!! note
    The build compiles the Rust extension from source using maturin, so it requires
    an internet connection (to download the Rust toolchain) and takes a few minutes.

## Troubleshooting

**"docker: command not found"**
:   Docker is not installed. Follow the [Prerequisites](#prerequisites) section above.

**"Unable to find image" when running**
:   You need to pull the image first: `docker pull ghcr.io/raeq/translit:latest`

**No output when piping input**
:   Make sure you're using the `-i` flag: `echo "text" | docker run -i ghcr.io/raeq/translit slugify`

**"permission denied" errors**
:   On Linux, you may need to run Docker with `sudo` or [add your user to the docker group](https://docs.docker.com/engine/install/linux-postinstall/).
