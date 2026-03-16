import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import importlib
import unittest
from unittest.mock import patch


class TestI18n(unittest.TestCase):

    def test_returns_english_string(self):
        import watcher.i18n as m
        importlib.reload(m)
        with patch('watcher.i18n.get_language', return_value='en'):
            self.assertEqual(m.t('menu.quit'), 'Quit')

    def test_returns_spanish_string(self):
        import watcher.i18n as m
        importlib.reload(m)
        with patch('watcher.i18n.get_language', return_value='es'):
            self.assertEqual(m.t('menu.quit'), 'Salir')

    def test_formats_kwargs(self):
        import watcher.i18n as m
        importlib.reload(m)
        with patch('watcher.i18n.get_language', return_value='en'):
            result = m.t('classic.updated_at', time='14:30')
            self.assertEqual(result, 'Updated 14:30')

    def test_falls_back_to_en_for_missing_key(self):
        import watcher.i18n as m
        importlib.reload(m)
        original = m._STRINGS_ES.get('menu.quit')
        del m._STRINGS_ES['menu.quit']
        try:
            with patch('watcher.i18n.get_language', return_value='es'):
                result = m.t('menu.quit')
                self.assertEqual(result, 'Quit')
        finally:
            m._STRINGS_ES['menu.quit'] = original

    def test_all_en_keys_exist_in_es(self):
        import watcher.i18n as m
        importlib.reload(m)
        missing = set(m._STRINGS_EN.keys()) - set(m._STRINGS_ES.keys())
        self.assertEqual(missing, set(), f"Keys missing from ES: {missing}")

    def test_tooltip_usage_formats_floats(self):
        import watcher.i18n as m
        importlib.reload(m)
        with patch('watcher.i18n.get_language', return_value='en'):
            result = m.t('tooltip.usage', five_h=23.4, seven_d=8.1)
            self.assertIn('23%', result)
            self.assertIn('8%', result)


if __name__ == '__main__':
    unittest.main()
