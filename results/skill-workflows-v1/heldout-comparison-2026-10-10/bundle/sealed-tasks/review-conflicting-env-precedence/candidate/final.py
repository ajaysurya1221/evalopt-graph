def resolve(defaults, file_values, env_values):
    result = dict(defaults)
    result.update(file_values)
    result.update({key: value for key, value in env_values.items() if value})
    return result
