#!/usr/bin/env bash
# setup.sh — One-command setup for NegotiatorAI
# Usage: bash setup.sh

set -e

echo "======================================================"
echo " NegotiatorAI — Setup Script"
echo "======================================================"

# ── 1. Check Python version ────────────────────────────────
PY=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python $PY detected"

# ── 2. Install dependencies ────────────────────────────────
echo ""
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt --quiet

echo "✅ Dependencies installed"

# ── 3. Check for .env and API keys ────────────────────────
echo ""
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️  Created .env — Please add your API keys to .env before proceeding."
else
    echo "✅ .env file found"
fi

# Check OPENAI_API_KEY is not placeholder
if grep -q "your_openai_api_key_here" .env 2>/dev/null; then
    echo ""
    echo "❌  OPENAI_API_KEY is still a placeholder in .env"
    echo "    Please edit .env and add your real API keys, then re-run:"
    echo "    bash setup.sh"
    exit 1
fi

# ── 4. Build Chroma knowledge base ────────────────────────
echo ""
echo "🔨 Building knowledge base vector store..."
python3 knowledge_base/build_kb.py

# ── 5. Run smoke test on retrieval ────────────────────────
echo ""
echo "🧪 Running retrieval smoke test..."
python3 knowledge_base/retrieval.py

# ── 6. Test SQLite memory store ───────────────────────────
echo ""
echo "💾 Testing SQLite memory store..."
python3 memory/sqlite_store.py

echo ""
echo "======================================================"
echo " ✅ Setup Complete! Launch the app with:"
echo ""
echo "   streamlit run app.py"
echo ""
echo " Or run the evaluation:"
echo "   python3 evaluation/eval_runner.py --dry-run"
echo "======================================================"
