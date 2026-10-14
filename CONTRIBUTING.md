# 🤝 Contributing to DepotVault

Thank you for your interest in contributing to **DepotVault**! 

## 🛠️ Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/KINGODIN1124/Manifest.git
   cd Manifest
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## 📜 Guidelines

- Maintain code style with standard Python PEP8 formatting.
- Ensure all sensitive data (such as session cookies or tokens) remains strictly excluded from git.
- Test your changes locally before submitting a Pull Request:
  ```bash
  python cli.py create-key --label "TestKey"
  ```
