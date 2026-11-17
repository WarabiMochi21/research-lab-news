"""Presentation only: keep numbered citations in stored research."""
import re


def display_text(text):
    # Protect URLs and Markdown links before removing numeric citation labels.
    protected = []
    def save(match):
        protected.append(match.group())
        return '\x00LINK' + str(len(protected)-1) + '\x00'
    value = re.sub(r'\[[^\]\n]+\]\(https?://[^\s)]+\)|https?://[^\s]+', save, str(text or ''))
    value = re.sub(r'\[\d{1,2}\]', '', value)
    value = re.sub(r'[ \t]+([,.;:!?])', r'\1', value)
    value = '\n'.join(re.sub(r'[ \t]{2,}', ' ', line).strip() for line in value.split('\n'))
    for i, link in enumerate(protected):
        value = value.replace('\x00LINK'+str(i)+'\x00', link)
    return value.strip()
