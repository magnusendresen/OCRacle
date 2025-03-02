def isType(a, b):
    return type(a) == b

# Create a function like above but where the input is always a string but checks if the string is a number
def isNumber(a):
    return a.strip().isnumeric()

print(isNumber("a"))  # False
print(isNumber(" 1"))  # True