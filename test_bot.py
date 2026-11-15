import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import bot

NOW=datetime(2026,11,15,12,tzinfo=timezone.utc)
CONFIG=json.loads((bot.ROOT/'config.json').read_text())
FEED=CONFIG['feeds'][0]
RSS=b'''<rss><channel>
<item><title>Inflation update</title><link>https://example.com/news?utm_source=rss</link><pubDate>Sun, 15 Nov 2026 10:00:00 GMT</pubDate><description>Test fixture only</description></item>
<item><title>Old earnings</title><link>https://example.com/old</link><pubDate>Fri, 13 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Future earnings</title><link>https://example.com/future</link><pubDate>Mon, 16 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Undated earnings</title><link>https://example.com/undated</link></item>
</channel></rss>'''

class BotTests(unittest.TestCase):
    def item(self):
        return bot.parse_feed(RSS,FEED,CONFIG,NOW)[0]

    def test_dates_and_tracking_url(self):
        items=bot.parse_feed(RSS,FEED,CONFIG,NOW)
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['url'],'https://example.com/news')

    def test_pending_not_retried(self):
        item=self.item()
        state={'items':{item['id']:{'headline_id':item['headline_id'],'status':'pending','attempted_at':NOW.isoformat()}}}
        self.assertEqual(bot.select_items([item],state,CONFIG,NOW),[])

    def test_cross_feed_exact_headline_deduplication(self):
        first=self.item()
        second=dict(first,id='different-url',url='https://example.org/syndicated')
        self.assertEqual(len(bot.select_items([first,second],{'items':{}},CONFIG,NOW)),1)

    def test_daily_budget(self):
        state={'items':{str(i):{'headline_id':str(i),'attempted_at':NOW.isoformat()} for i in range(12)}}
        self.assertEqual(bot.select_items([self.item()],state,CONFIG,NOW),[])

    def test_payload_labels_and_mentions(self):
        item=self.item()
        item['title']='@everyone earnings'
        payload=bot.format_message(item)
        self.assertEqual(payload['allowed_mentions'],{'parse':[]})
        self.assertIn('tanpa API',payload['embeds'][0]['footer']['text'])
        self.assertLess(len(payload['embeds'][0]['description']),4096)
        draft={'headline':'Draft','summary':'Facts','caption':'Caption'}
        self.assertIn('DRAFT AI',bot.format_message(item,draft)['embeds'][0]['footer']['text'])

    def test_webhook_hostname_and_destination(self):
        with self.assertRaises(ValueError):
            bot.validate_webhook('https://discord.com.evil.example/api/webhooks/123/secret')
        with patch('bot.http',return_value=b'{"channel_id":"456"}'):
            with self.assertRaises(ValueError):
                bot.verify_destination('https://discord.com/api/webhooks/123/secret','789')

    def test_delivery_timeout_does_not_repeat(self):
        with patch('bot.http',side_effect=TimeoutError) as call:
            with self.assertRaises(RuntimeError):
                bot.deliver('https://discord.com/api/webhooks/123/secret',{})
            self.assertEqual(call.call_count,1)

    def test_preview_is_not_marked_sent(self):
        with tempfile.TemporaryDirectory() as folder:
            args=SimpleNamespace(state_dir=str(Path(folder)/'state'),output_dir=str(Path(folder)/'out'),send=False,git_sync=False)
            with patch('bot.utcnow',return_value=NOW), patch('bot.http',return_value=RSS), patch.dict('os.environ',{'GEMINI_API_KEY':''}):
                bot.run(args)
            self.assertFalse((Path(folder)/'state'/'state.json').exists())
            report=json.loads((Path(folder)/'out'/'run-report.json').read_text())
            self.assertEqual(report['mode'],'preview')
            self.assertEqual(report['selected'],1)

    def test_failed_post_has_persistent_pending_record(self):
        with tempfile.TemporaryDirectory() as folder:
            args=SimpleNamespace(state_dir=str(Path(folder)/'state'),output_dir=str(Path(folder)/'out'),send=True,git_sync=False)
            with patch('bot.utcnow',return_value=NOW), patch('bot.http',return_value=RSS), patch('bot.verify_destination'), patch('bot.deliver',side_effect=RuntimeError('uncertain')), patch.dict('os.environ',{'GEMINI_API_KEY':''}):
                with self.assertRaises(RuntimeError):
                    bot.run(args)
            state=json.loads((Path(folder)/'state'/'state.json').read_text())
            self.assertEqual(next(iter(state['items'].values()))['status'],'pending')

if __name__=='__main__':
    unittest.main()
