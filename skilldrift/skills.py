import re

SKILLS = [
    "python",
    "javascript",
    "typescript",
    "react",
    "vue",
    "node.js",
    "rust",
    "golang",
    "java",
    "tensorflow",
    "pytorch",
    "llm",
    "rag",
    "transformers",
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "spark",
    "kafka",
    "sql",
    "postgresql",
    "redis",
    "fastapi",
    "solr",
    "elasticsearch",
]

SKILL_PATTERNS = {
    "node.js": r"(?i)(?<![\w])node(?:\.js|js)?(?![\w])",
    "golang": r"(?i)(?<![\w])(?:go|golang)(?![\w])",
    "react": r"(?i)(?<![\w])react(?:\.js|js)?(?![\w])",
    "vue": r"(?i)(?<![\w])vue(?:\.js|js)?(?![\w])",
    "java": r"(?i)(?<![\w])java(?!script)",
    "javascript": r"(?i)(?<![\w])(?:javascript|java\s*script|js)(?![\w])",
    "typescript": r"(?i)(?<![\w])(?:typescript|type\s*script|ts)(?![\w])",
    "sql": r"(?i)(?<![\w])sql(?![\w])",
    "llm": r"(?i)(?<![\w])(?:llms?|large language models?)(?![\w])",
    "rag": r"(?i)(?<![\w])(?:rag|retrieval[- ]augmented generation)(?![\w])",
}


def pattern_for(skill: str) -> str:
    return SKILL_PATTERNS.get(skill, rf"(?i)(?<![\w]){re.escape(skill)}(?![\w])")
