import numpy as np

def removeRandomLetter(data, percentage):
    for i in range(len(data)):
        if np.random.rand() < percentage:
            rand_index = np.random.randint(len(data[i]))
            data[i] = data[i][:rand_index] + data[i][rand_index+1:]
    return data

def addRandomSpaces(data, percentage):
    for i in range(len(data)):
        if np.random.rand() < percentage:
            rand_index = np.random.randint(len(data[i]))
            data[i] = data[i][:rand_index] + ' ' + data[i][rand_index:]
    return data

def misinterpretLetters(data, percentage):
    similarCharacters = [
        {'0', 'O', 'D', 'Q'}, {'1', 'I', 'l', '|', '!', '7'}, {'2', 'Z', '5'}, {'3', 'E', '8'},
        {'4', 'A', 'H'}, {'5', 'S', '2'}, {'6', 'b', 'G'}, {'7', 'T', '1'}, {'8', 'B', '3'},
        {'9', 'g', 'q', 'P'}, {'a', 'e', 'o', 'd'}, {'b', '6', 'h'}, {'c', 'k', 'e'}, {'d', 'cl', 'a'},
        {'e', 'a', 'c'}, {'f', 't', 'r'}, {'g', '9', 'q'}, {'h', 'n', 'b'}, {'i', '1', 'j', 'l'},
        {'j', 'i', 'y'}, {'k', 'c', 'x'}, {'l', '1', 'i'}, {'m', 'n', 'rn'}, {'n', 'm', 'h'},
        {'o', '0', 'a'}, {'p', 'q', '9'}, {'q', 'p', 'g'}, {'r', 'n', 'f'}, {'s', '5', 'z'},
        {'t', 'f', '7'}, {'u', 'v', 'w'}, {'v', 'u', 'y'}, {'w', 'vv', 'u'}, {'x', 'ks', 'k'},
        {'y', 'j', 'v'}, {'z', '2', 's'}, {'A', '4', 'H'}, {'B', '8', '3'}, {'C', 'G', 'O'},
        {'D', '0', 'O'}, {'E', '3', '8'}, {'F', 'P', 'T'}, {'G', '6', 'C'}, {'H', '4', 'A'},
        {'I', '1', 'l'}, {'J', 'L', 'i'}, {'K', 'X', 'k'}, {'L', '1', 'J'}, {'M', 'N', 'W'},
        {'N', 'M', 'H'}, {'O', '0', 'Q'}, {'P', 'R', '9'}, {'Q', 'O', '0'}, {'R', 'P', 'K'},
        {'S', '5', '2'}, {'T', '7', 'F'}, {'U', 'V', 'W'}, {'V', 'U', 'Y'}, {'W', 'VV', 'M'},
        {'X', 'K', 'ks'}, {'Y', 'V', 'j'}, {'Z', '2', 's'},{'À', 'Á', 'Â', 'Ã', 'Ä', 'Å', 'A'}, {'à', 'á', 'â', 'ã', 'ä', 'å', 'a'},
        {'È', 'É', 'Ê', 'Ë', 'E'}, {'è', 'é', 'ê', 'ë', 'e'},
        {'Ì', 'Í', 'Î', 'Ï', 'I'}, {'ì', 'í', 'î', 'ï', 'i'},
        {'Ò', 'Ó', 'Ô', 'Õ', 'Ö', 'Ø', 'O'}, {'ò', 'ó', 'ô', 'õ', 'ö', 'ø', 'o'},
        {'Ù', 'Ú', 'Û', 'Ü', 'U'}, {'ù', 'ú', 'û', 'ü', 'u'},
        {'Ç', 'C'}, {'ç', 'c'}, {'Ñ', 'N'}, {'ñ', 'n'}
    ]
    for i in range(len(data)):
        new_string = list(data[i])
        for k in range(len(new_string)):
            if np.random.rand() < percentage:
                for l in range(len(similarCharacters)):
                    if new_string[k] in similarCharacters[l]:
                        new_string[k] = np.random.choice(list(similarCharacters[l]))
                        break
        data[i] = ''.join(new_string)
    return data

def simulateOCRMistakes(data, percentage):
    data = removeRandomLetter(data, percentage)
    data = addRandomSpaces(data, percentage)
    data = misinterpretLetters(data, percentage)
    return data

def readCSVfile(filepath):
    with open(filepath, 'r') as file:
        data = file.readlines()
        
    # Multipliser og flatt ut listen
    data = [line.strip() for line in data] * 10
    return data

formuleringer = readCSVfile('dataset/formuleringer.csv')

resultat = simulateOCRMistakes(formuleringer, 0.5)

for line in resultat:
    print(line)
