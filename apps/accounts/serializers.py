from django.contrib.auth import password_validation
from rest_framework import serializers

from .models import Profile, User


class BrowserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class BrowserSessionSerializer(serializers.Serializer):
    csrf_token = serializers.CharField()
    authenticated = serializers.BooleanField()


class RegisterSerializer(serializers.ModelSerializer):
    # Declared explicitly to drop DRF's case-sensitive UniqueValidator; see validate_email.
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    role = serializers.ChoiceField(choices=User.Role.choices, default=User.Role.ATTENDEE)

    class Meta:
        model = User
        fields = ["id", "email", "password", "first_name", "last_name", "role"]
        read_only_fields = ["id"]

    def validate_email(self, value):
        email = User.objects.normalize_email(value)
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate(self, attrs):
        user = User(**{k: v for k, v in attrs.items() if k != "password"})
        password_validation.validate_password(attrs["password"], user)
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["phone", "bio", "city"]


class MeSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(required=False)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_staff",
            "date_joined",
            "profile",
        ]
        read_only_fields = ["id", "email", "role", "is_staff", "date_joined"]

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)
        instance = super().update(instance, validated_data)
        if profile_data:
            for field, value in profile_data.items():
                setattr(instance.profile, field, value)
            instance.profile.save(update_fields=[*profile_data, "updated_at"])
        return instance
