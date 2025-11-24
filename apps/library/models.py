import re
from django.core.exceptions import ValidationError
from django.db import models


ISBN13_REGEX = re.compile(r"^97[89]-\d+-\d+-\d+-\d$")


def validate_isbn13(value: str) -> None:
    """
    校验 ISBN-13 格式：
    - 格式：978-组号-出版社-序号-校验位
    - 总位数：13 位数字（去掉连字符后）
    - 校验位：符合 ISBN-13 加权算法
    """
    if not ISBN13_REGEX.match(value):
        raise ValidationError("ISBN 必须符合 978-组号-出版社-序号-校验位 的格式")

    digits = value.replace("-", "")
    if len(digits) != 13 or not digits.isdigit():
        raise ValidationError("ISBN 必须是 13 位数字（不含连字符）")

    checksum = sum((1 if idx % 2 == 0 else 3) * int(d) for idx, d in enumerate(digits[:-1]))
    check_digit = (10 - (checksum % 10)) % 10
    if check_digit != int(digits[-1]):
        raise ValidationError("ISBN 校验位不正确")


class Book(models.Model):
    title = models.CharField(max_length=200, verbose_name="书名")
    author = models.CharField(max_length=120, blank=True, verbose_name="作者")
    isbn = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        verbose_name="ISBN",
        validators=[validate_isbn13],
        help_text="格式：978-组号-出版社-序号-校验位，含校验位共13位",
    )
    publisher = models.CharField(max_length=120, blank=True, verbose_name="出版社")
    category = models.CharField(max_length=80, blank=True, db_index=True, verbose_name="分类")
    total_copies = models.PositiveIntegerField(default=1, verbose_name="馆藏总数")
    available_copies = models.PositiveIntegerField(default=1, verbose_name="可借数量")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "图书"
        verbose_name_plural = "图书"
        indexes = [
            models.Index(fields=["category"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.isbn})"


# Create your models here.
