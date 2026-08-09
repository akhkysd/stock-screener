import markdown as markdown_lib

BODY_FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Hiragino Sans', 'Hiragino Kaku Gothic ProN', "
    "'Yu Gothic', 'Noto Sans JP', sans-serif"
)

STYLE = f"""
body {{ font-family: {BODY_FONT_STACK}; color: #20242e; background: #f6f3ec;
        margin: 0; padding: 24px 12px; }}
.container {{ max-width: 720px; margin: 0 auto; background: #ffffff;
              border: 1px solid #e1dcce; border-radius: 8px; padding: 24px; }}
h1 {{ font-size: 20px; margin: 0 0 16px; }}
h2 {{ font-size: 16px; margin: 24px 0 8px; border-bottom: 1px solid #e1dcce;
      padding-bottom: 4px; }}
table {{ border-collapse: collapse; width: 100%; margin: 8px 0 16px; font-size: 14px; }}
th, td {{ border: 1px solid #e1dcce; padding: 6px 10px; text-align: left; }}
th {{ background: #f6f3ec; }}
p {{ font-size: 14px; line-height: 1.6; }}
"""


def markdown_to_email_html(markdown_text: str, title: str) -> str:
    body = markdown_lib.markdown(markdown_text, extensions=["tables"])
    return (
        '<html><head><meta charset="utf-8"><title>'
        f"{title}</title><style>{STYLE}</style></head>"
        f'<body><div class="container">{body}</div></body></html>'
    )
