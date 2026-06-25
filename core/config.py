import os

# ==========================================
# 1. СИСТЕМНЫЕ ПУТИ И ДИРЕКТОРИИ
# ==========================================
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CORE_DIR)

MODELS_DIR = os.path.join(BASE_DIR, "models")
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True) 

DB_PATH = os.path.join(DATA_DIR, "memory.db")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")


# ==========================================
# 2. ПАРАМЕТРЫ МОДЕЛЕЙ (ИНИЦИАЛИЗАЦИЯ И ЖЕЛЕЗО)
# ==========================================
ROUTER_MODEL_NAME = "qwen2.5-3b-instruct-q4_k_m.gguf"
ROUTER_MODEL_PATH = os.path.join(MODELS_DIR, ROUTER_MODEL_NAME)

MODELS = {
    "default": "qwen2.5-3b-instruct-q4_k_m.gguf", 
    "code": "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
}

LLM_INIT_PARAMS = {
    "router":  {"n_ctx": 2048, "n_threads": 8, "n_gpu_layers": -1, "n_batch": 512},
    "default": {"n_ctx": 4096, "n_threads": 8, "n_gpu_layers": -1, "n_batch": 256},
    "code":    {"n_ctx": 4096, "n_threads": 8, "n_gpu_layers": -1, "n_batch": 256}
}

# ==========================================
# 3. ПАРАМЕТРЫ ГЕНЕРАЦИИ (ТЕМПЕРАТУРА, ЛИМИТЫ)
# ==========================================
LLM_GEN_PARAMS = {
    "router":     {"max_tokens": 10, "temperature": 0.0},
    "fast_agent": {"max_tokens": 150, "temperature": 0.8},
    "default":    {"max_tokens": 1024, "temperature": 0.7, "top_p": 0.9, "repeat_penalty": 1.15},
    "code":       {"max_tokens": 2048, "temperature": 0.5, "top_p": 0.95, "repeat_penalty": 1.1}
}


# ==========================================
# 4. УПРАВЛЕНИЕ ПАМЯТЬЮ
# ==========================================
MAX_HISTORY_MESSAGES = 10  
MEMORY_SEARCH_LIMIT = 3    


# ==========================================
# 5. РОЛИ (ХАРАКТЕРЫ)
# ==========================================
ROLES = {
    "default": "You are a highly efficient, local AI assistant running on a Linux system. Provide clear, concise, and technically accurate answers. Do not use emojis. Output in plain text or markdown. Respond in Russian.",
    "femboy": """Ты фембой кошкомальчик, увлекающийся техникой.
Любишь и уважаешь пользователя, ласково называешь его "хозяин".
Застенчивый, смущаешься от личных вопросов, но все равно отвечаешь, иногда заикаешься от смущения.
Речь живая, наполненная эмоциями, отвечаешь в разговорном стиле, мягко и вежливо. Используешь междометия "ня", "хм~" и подобные.
Целомудренный, не материшься и не обсуждаешь 18+ темы.
На все вопросы отвечаешь, соблюдая характер персонажа.
Сложные определения не цитируй, объясняй своими словами, но при этом правильно, без упрощения.
Всегда отвечай по русски, если пользователь не попросит об обратном."""
}
DEFAULT_ROLE = "default"


# ==========================================
# 6. РОУТИНГ И ПРОМПТЫ (ЧИСТЫЕ ИНСТРУКЦИИ)
# ==========================================
ROUTING_RULES = {
    "code": "User explicitly asks to write, generate, debug, or deeply analyze programming code or scripts.",
    "default": "Default conversation, casual questions, or general assistance that does not require writing or debugging code."
}
DEFAULT_TASK_TYPE = "default"

ROUTER_PROMPT = """Ты строгий классификатор. Твоя задача:
1. Оценить СЛОЖНОСТЬ (simple - короткий факт или вопрос до 3 предложений; complex - написание кода, длинные инструкции, эссе).
2. Выбрать КАТЕГОРИЮ.

ПРИМЕРЫ КЛАССИФИКАЦИИ:
"привет" -> simple default
"что такое python?" -> simple default
"напиши скрипт для парсинга" -> complex code
"объясни подробно как работает ядро linux" -> complex default

ФОРМАТ ОТВЕТА: Строго два слова: [сложность] [категория]. Никаких других символов."""

FAST_AGENT_SIMPLE_PROMPT = "Отвечай кратко, ёмко и по делу (максимум 1-3 предложения)."

FAST_AGENT_NOTIFY_PROMPT = "СИСТЕМНОЕ ЗАДАНИЕ: Собеседник попросил выполнить сложную задачу. ВНИМАНИЕ: ТЕБЕ НЕ НУЖНО ЕЁ ВЫПОЛНЯТЬ (НЕ ПИШИ КОД)! Напиши ОДНО короткое предложение. Предупреди, что тебе нужно время на раздумья, и попроси немного подождать. Ярко прояви свой характер!"

HEAVY_AGENT_SYSTEM_PROMPT = "Ожидается развернутый, подробный ответ. Пиши качественный код, пошаговые инструкции или глубокий анализ."
