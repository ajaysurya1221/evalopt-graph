def allowed(member):
    return not member.startswith("/") and "\\" not in member
