from django.core.management.base import BaseCommand, CommandError

from market.services import expire_orders


class Command(BaseCommand):
    help = "受取期限を過ぎた予約を期限切れにし、在庫を戻します。"

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100)

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        if batch_size < 1:
            raise CommandError("--batch-size は1以上で指定してください。")
        count = expire_orders(batch_size=batch_size)
        self.stdout.write(self.style.SUCCESS(f"期限切れに更新した注文: {count}件"))
