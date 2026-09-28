"""Keep existing Markdown Viewer preferences after the rename."""

from PySide6.QtCore import QSettings

from app import settings as settings_module


def test_marxdown_imports_existing_preferences_once(tmp_path, monkeypatch):
    old_store = QSettings(str(tmp_path / "old.ini"), QSettings.Format.IniFormat)
    new_store = QSettings(str(tmp_path / "new.ini"), QSettings.Format.IniFormat)
    recent = tmp_path / "中文.md"
    recent.write_text("# 中文", encoding="utf-8")
    old_store.setValue("theme", "dark")
    old_store.setValue("font_size", 18)
    old_store.setValue("recent_files", [str(recent)])

    def fake_settings(organization, application):
        if (organization, application) == ("Marxdown", "Marxdown"):
            return new_store
        assert (organization, application) == ("MarkdownViewer", "Markdown Viewer")
        return old_store

    monkeypatch.setattr(settings_module, "QSettings", fake_settings)
    settings = settings_module.AppSettings()

    assert new_store.value("theme") == "dark"
    assert settings.font_size == 18
    assert settings.recent_files == [recent]
