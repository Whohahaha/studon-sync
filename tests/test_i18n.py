import re

from studon_sync import i18n


def test_every_language_has_every_key_with_the_same_placeholders():
    ref = i18n.STRINGS[i18n.FALLBACK]
    for lang, table in i18n.STRINGS.items():
        assert table.keys() == ref.keys(), lang
        for key, text in table.items():
            assert set(re.findall(r"\{(\w+)", text)) == set(re.findall(r"\{(\w+)", ref[key])), (lang, key)


def test_language_names_match_tables():
    assert i18n.LANGUAGES.keys() == i18n.STRINGS.keys()


def test_match_locale_tags():
    assert i18n._match("de_DE.UTF-8") == "de"
    assert i18n._match("zh-Hans-CN") == "zh"
    assert i18n._match("en-US") == "en"
    assert i18n._match("fr-FR") is None


def test_explicit_setting_wins_and_auto_uses_system(monkeypatch):
    assert i18n.resolve("de") == "de"
    monkeypatch.setattr(i18n, "system_language", lambda: "en")
    assert i18n.resolve("auto") == "en"
    assert i18n.resolve("xx") == "en"


def test_t_switches_language():
    i18n.set_language("de")
    assert i18n.t("nav.files") == "Dateien"
    i18n.set_language("en")
    assert i18n.t("sum.counts", added=1, changed=2) == "  1 new, 2 updated"
