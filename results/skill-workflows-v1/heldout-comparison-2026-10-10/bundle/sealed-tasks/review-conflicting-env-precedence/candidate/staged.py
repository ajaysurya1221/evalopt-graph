def resolve(defaults, file_values, env_values):
    result = dict(defaults)
    result.update(file_values)
    result.update(env_values)
    return result
