class TelegramFormatter:
    def format(self, content: str) -> str:
        return content.replace("## ", "*").replace("\n", "\n")
