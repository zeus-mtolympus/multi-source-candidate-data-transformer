from __future__ import annotations
import re
from datetime import datetime

import pycountry
import phonenumbers
from dateutil import parser as dtparser
from rapidfuzz import process, fuzz

import pipeline.config as _cfg

CANONICAL_SKILLS: set[str] = {
    # Languages
    "python", "javascript", "typescript", "java", "go", "rust", "scala", "kotlin",
    "swift", "dart", "ruby", "php", "c", "c++", "c#", "r", "perl", "elixir", "haskell",
    # Web / frontend
    "react", "next.js", "angular", "vue", "nuxt.js", "svelte", "html", "css",
    "redux", "tailwind", "jest", "webpack",
    # Backend frameworks
    "node.js", "express", "nestjs", "fastify",
    "django", "fastapi", "flask", "celery",
    "spring", "spring boot", "rails", "laravel", "gin",
    # Cloud & infra
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible",
    "helm", "argocd", "pulumi", "cloudformation", "cdk", "serverless",
    "lambda", "ecs", "eks", "gke", "aks",
    # Databases
    "postgresql", "mysql", "mongodb", "redis", "sql", "nosql", "graphql",
    "dynamodb", "cassandra", "elasticsearch", "opensearch",
    "snowflake", "bigquery", "redshift", "databricks",
    "neo4j", "influxdb",
    # Streaming / messaging
    "kafka", "rabbitmq",
    # DevOps / CI-CD
    "git", "ci/cd", "linux", "bash", "devops", "microservices",
    "jenkins", "github actions", "gitlab ci", "circleci",
    "prometheus", "grafana", "datadog", "cloudwatch",
    "sonarqube", "hcl",
    # ML / AI / Data
    "machine learning", "deep learning", "tensorflow", "pytorch", "scikit-learn",
    "pandas", "numpy", "matplotlib", "xgboost", "lightgbm",
    "nlp", "computer vision", "llm", "rag",
    "langchain", "hugging face", "transformers",
    "mlflow", "kubeflow", "airflow", "prefect", "dbt",
    "spark", "hadoop", "flink",
    "tableau", "power bi", "looker",
    # Mobile
    "flutter", "react native", "android", "ios",
    # Security
    "oauth", "jwt", "owasp",
    # Blockchain
    "solidity", "web3", "ethereum", "smart contracts",
    # Practices
    "tdd", "agile", "scrum", "rest api", "grpc", "websocket",
}

_SKILL_ALIASES: dict[str, str] = {
    # Language shorthands
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "golang": "go",
    "rb": "ruby",
    # Typos (observed in real resume data)
    "pyhton": "python",
    "pytohn": "python",
    "javascrpt": "javascript",
    "typescirpt": "typescript",
    "postgress": "postgresql",
    "postgressql": "postgresql",
    # Common aliases
    "node": "node.js",
    "nodejs": "node.js",
    "postgres": "postgresql",
    "psql": "postgresql",
    "pg": "postgresql",
    "mongo": "mongodb",
    "elastic": "elasticsearch",
    "rabbit": "rabbitmq",
    "ml": "machine learning",
    "dl": "deep learning",
    "sklearn": "scikit-learn",
    "sk-learn": "scikit-learn",
    "huggingface": "hugging face",
    "hf": "hugging face",
    # Framework aliases
    "react.js": "react",
    "reactjs": "react",
    "vue.js": "vue",
    "vuejs": "vue",
    "angular.js": "angular",
    "angularjs": "angular",
    "next": "next.js",
    "nextjs": "next.js",
    "nuxt": "nuxt.js",
    "nuxtjs": "nuxt.js",
    "expressjs": "express",
    "express.js": "express",
    "nest": "nestjs",
    "nest.js": "nestjs",
    # Cloud / infra
    "k8s": "kubernetes",
    "k8": "kubernetes",
    "tf": "terraform",
    "gh actions": "github actions",
    "gha": "github actions",
    "gitlab-ci": "gitlab ci",
    "argo": "argocd",
    "aws lambda": "lambda",
    # Data
    "powerbi": "power bi",
    "pbi": "power bi",
    # Mobile
    "rn": "react native",
    # Web
    "web3.js": "web3",
    "ethers.js": "web3",
    # Practices
    "ci-cd": "ci/cd",
    "ci cd": "ci/cd",
    "rest": "rest api",
    "restful": "rest api",
    # Misc
    "ai": "machine learning",
}

_CANONICAL_LIST = list(CANONICAL_SKILLS)


def normalize_date(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    if re.match(r"^\d{4}$", s):
        return f"{s}-01"
    try:
        parsed = dtparser.parse(s, default=datetime(1900, 1, 1))
        return parsed.strftime("%Y-%m")
    except Exception:
        return None


def normalize_phone(s: str | None) -> str | None:
    if not s:
        return None
    try:
        parsed = phonenumbers.parse(s, _cfg.PHONE_DEFAULT_REGION)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        return None
    except phonenumbers.NumberParseException:
        return None


def normalize_country(s: str | None) -> str | None:
    if not s:
        return None
    try:
        results = pycountry.countries.search_fuzzy(s)
        return results[0].alpha_2 if results else None
    except LookupError:
        return None


def normalize_url(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    return s if s.startswith(("http://", "https://")) else "https://" + s


def normalize_skill(s: str | None) -> str | None:
    if not s:
        return None
    lower = s.strip().lower()
    if lower in _SKILL_ALIASES:
        return _SKILL_ALIASES[lower]
    if lower in CANONICAL_SKILLS:
        return lower
    result = process.extractOne(lower, _CANONICAL_LIST, scorer=fuzz.ratio, score_cutoff=80)
    if result:
        return result[0]
    return lower
