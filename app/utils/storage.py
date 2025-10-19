from typing import Dict, Set

# Простейшее in-memory хранилище
user_items: Dict[int, Dict[str, float]] = {}  # user_id -> {item_id: last_price}
user_searches: Dict[int, Set[str]] = {}       # user_id -> set of search queries
