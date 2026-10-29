from django.core.management.base import BaseCommand

from market.services import seed_demo_data


class Command(BaseCommand):
    help = "アカウントを作成せず、繰り返し実行できるデモ商品データを作成します。"

    def handle(self, *args, **options):
        created = seed_demo_data()
        summary = ", ".join(f"{key}={value}" for key, value in created.items())
        self.stdout.write(self.style.SUCCESS(f"デモデータ作成完了: {summary}"))
