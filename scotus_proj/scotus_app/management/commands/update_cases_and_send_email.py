from django.core.management.base import BaseCommand
from ...crons import UpdateCases, SendEmail


class Command(BaseCommand):
    help = "Updates cases and send email"

    def add_arguments(self, parser):
        return

    def handle(self, *args, **options):
        updater = UpdateCases()
        updater.do()
        emailer = SendEmail()
        emailer.do()
        self.stdout.write("Updated cases and sent email!")
