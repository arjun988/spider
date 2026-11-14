FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    ripgrep \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install core deps + Tree-sitter language packs (required for symbol indexing).
# Fail the build if optional language grammars cannot import.
RUN pip install --no-cache-dir -r requirements.txt \
    && python -c "import tree_sitter, tree_sitter_python, tree_sitter_javascript, tree_sitter_typescript, tree_sitter_go, tree_sitter_rust, tree_sitter_java, tree_sitter_c, tree_sitter_cpp, tree_sitter_c_sharp, tree_sitter_ruby, tree_sitter_php, tree_sitter_kotlin; print('tree-sitter packs ok')"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]