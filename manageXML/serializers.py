from rest_framework import serializers
from .models import *


class LexemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lexeme
        fields = ("id", "lexeme", "pos", "homoId", "language")
