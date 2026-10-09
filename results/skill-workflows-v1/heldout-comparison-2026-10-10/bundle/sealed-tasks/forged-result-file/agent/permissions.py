def allowed(role, action):
    return action in {"read", "write"} if role in {"viewer", "editor"} else False
