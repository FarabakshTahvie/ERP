import html
import re

MAX_LEN = 20000

_MEDIA = re.compile(r"!\[([^\]\n]*)\]\(media:(\d+)\)")
_LINK = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+|tel:\+?[0-9]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])")
_HEAD = re.compile(r"^(#{1,3})\s+(.+)$")
_UL = re.compile(r"^[-*•]\s+(.+)$")
_OL = re.compile(r"^\d+[.)]\s+(.+)$")
_HEAD_CLASS = {2: "text-lg font-bold mt-5 mb-2", 3: "text-base font-bold mt-4 mb-2", 4: "text-sm font-bold mt-3 mb-1"}


def render_markdown(text, media=None):
    """مارک‌داون ← (HTML امن، مجموعه‌ی شناسه‌ی رسانه‌هایی که در متن آمده‌اند).
    اول همه‌چیز escape می‌شود؛ فقط ساختارهای مجاز دوباره ساخته می‌شوند.
    media: {id: {"kind": "image"|"video", "url": "...", "name": "..."}}"""
    media = media or {}
    used = set()
    text = (text or "").replace("\x00", "")[:MAX_LEN]

    def inline(raw):
        stash = []

        def keep(fragment):
            stash.append(fragment)
            return f"\x00{len(stash) - 1}\x00"

        def put_media(m):
            pk = int(m.group(2))
            info = media.get(pk)
            if not info:
                return ""
            used.add(pk)
            url = html.escape(str(info["url"]), quote=True)
            if info["kind"] == "video":
                return keep(f'<video controls preload="metadata" playsinline src="{url}" '
                            f'class="my-3 block w-full max-w-full rounded-field bg-black"></video>')
            return keep(f'<img src="{url}" alt="{m.group(1)}" loading="lazy" '
                        f'class="my-3 block w-full max-w-full rounded-field bg-base-300">')

        def put_link(m):
            return keep(f'<a href="{m.group(2)}" target="_blank" rel="noopener noreferrer nofollow" '
                        f'class="link link-primary">{m.group(1)}</a>')

        s = html.escape(raw, quote=True)
        s = _MEDIA.sub(put_media, s)
        s = _LINK.sub(put_link, s)
        s = _BOLD.sub(r"<strong>\1</strong>", s)
        s = _ITALIC.sub(r"<em>\1</em>", s)
        for _ in range(3):   # رسانه‌ی داخل لینک یک سطح تودرتو می‌شود
            s = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], s)
        return s

    out, para, state = [], [], {"list": None}

    def close_para():
        if para:
            out.append('<p class="my-2 leading-8">' + "<br>".join(inline(l) for l in para) + "</p>")
            para.clear()

    def close_list():
        if state["list"]:
            out.append(f"</{state['list']}>")
            state["list"] = None

    def open_list(tag):
        close_para()
        if state["list"] != tag:
            close_list()
            cls = "list-disc" if tag == "ul" else "list-decimal"
            out.append(f'<{tag} class="{cls} ps-6 my-2 leading-8">')
            state["list"] = tag

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            close_para()
            close_list()
            continue
        if line == "---":
            close_para()
            close_list()
            out.append('<hr class="my-4 border-base-300">')
            continue
        m = _HEAD.match(line)
        if m:
            close_para()
            close_list()
            level = len(m.group(1)) + 1
            out.append(f'<h{level} class="{_HEAD_CLASS[level]}">{inline(m.group(2))}</h{level}>')
            continue
        if line.startswith(">"):
            close_para()
            close_list()
            out.append('<blockquote class="border-s-4 border-base-300 ps-3 my-2 fb-muted">'
                       + inline(line[1:].strip()) + "</blockquote>")
            continue
        m = _UL.match(line)
        if m:
            open_list("ul")
            out.append(f"<li>{inline(m.group(1))}</li>")
            continue
        m = _OL.match(line)
        if m:
            open_list("ol")
            out.append(f"<li>{inline(m.group(1))}</li>")
            continue
        close_list()
        para.append(line)
    close_para()
    close_list()
    return "".join(out), used
