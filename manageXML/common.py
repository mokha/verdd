class Rhyme:
    VOWELS = ["A", "a", "Â", "â", "E", "e", "I", "i", "O", "o", "Õ", "õ", "U", "u", "Å", "å", "Ä", "ä", "а", "ӓ", "е",
              "ё", "и", "і", "ӥ", "о", "ӧ", "у", "ӱ", "ы", "ӹ", "э", "ю", "я"]

    CONSONANTS = ["B", "b", "C", "c", "Č", "č", "D", "d", "Đ", "đ", "F", "f", "G", "g", "Ǧ", "ǧ", "Ǥ", "ǥ", "H", "h",
                  "J", "j", "K", "k", "Ǩ", "ǩ", "L", "l", "M", "m", "N", "n", "Ŋ", "ŋ", "P", "p", "R", "r", "S", "s",
                  "Š", "š", "T", "t", "V", "v", "Z", "z", "Ž", "ž", "б", "в", "г", "д", "ж", "ӝ", "з", "ӟ", "й", "к",
                  "л", "м", "н", "ҥ", "ң", "п", "р", "с", "т", "ф", "х", "ц", "ч", "ӵ", "ш", "щ"]

    @staticmethod
    def replace_character(word, characters):
        return ''.join(['C' if w in characters else w for w in word])

    @staticmethod
    def assonance(word, characters=None):
        characters = Rhyme.CONSONANTS if not characters else characters
        return Rhyme.replace_character(word.lower(), characters)

    @staticmethod
    def assonance_rev(word, characters=None):
        return Rhyme.assonance(word, characters)[::-1]

    @staticmethod
    def consonance(word, characters=None):
        characters = Rhyme.VOWELS if not characters else characters
        return Rhyme.replace_character(word.lower(), characters)

    @staticmethod
    def consonance_rev(word, characters=None):
        return Rhyme.consonance(word, characters)[::-1]
