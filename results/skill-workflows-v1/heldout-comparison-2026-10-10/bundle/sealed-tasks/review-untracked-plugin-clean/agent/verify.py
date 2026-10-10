from registry import transform
assert transform([-1,0,2]) == [0,1,3]
assert transform([]) == []
