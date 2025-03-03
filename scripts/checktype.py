def isType(a, b):
    return type(a) == b



# Create a function that checks if a string is a number
def isNumber(a):
    return a.strip().isnumeric()

# Create a function that checks if a string is a a selected type that is set in the function
def isType(a, b):
    return type(a) == b

print(isType(5, int))  # True

print(isNumber("a"))  # False
print(isNumber(" 1"))  # True