def resolve(defaults, file_values, env_values):
    return {**defaults, **file_values, **env_values}
