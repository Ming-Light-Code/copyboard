"""
Copyboard — 主题管理模块（精致调色板）
"""

THEMES = {
    'light': {
        'name': '浅色',
        'colors': {
            'bg_primary': '#FCFCFD',
            'bg_secondary': '#F2F4F7',
            'bg_tertiary': '#E4E7EC',
            'bg_card': '#FFFFFF',
            'bg_card_hover': '#F7F8FB',
            'bg_pinned': '#F5F7FF',
            'bg_input': '#F0F1F5',
            'text_primary': '#101214',
            'text_secondary': '#5E6773',
            'text_muted': '#8B95A1',
            'accent': '#3451E2',
            'accent_hover': '#2742C7',
            'accent_light': '#EDF0FD',
            'border': '#DDE1E6',
            'border_light': '#EDEFF3',
            'danger': '#E5484D',
            'favorite': '#F0A000',
            'favorite_light': '#FFF6E5',
            'pin': '#7C5CF0',
            'pin_light': '#F3F0FF',
            'success': '#3CB179',
            'shadow': '#00000010',
            'header_bg': '#FCFCFD',
            'overlay': '#44000000',
            'divider': '#EAECF0',
            'type_text': '#3451E2',
            'type_image': '#3CB179',
            'type_file': '#F0A000',
            'type_folder': '#E0A400',
            'scrollbar': '#C8CCD4',
            'scrollbar_hover': '#A0A6B0',
        }
    },
    'dark': {
        'name': '深色',
        'colors': {
            'bg_primary': '#161618',
            'bg_secondary': '#1C1C1F',
            'bg_tertiary': '#252528',
            'bg_card': '#1E1E21',
            'bg_card_hover': '#242427',
            'bg_pinned': '#1E1E2A',
            'bg_input': '#222225',
            'text_primary': '#ECEDEE',
            'text_secondary': '#9DA0A8',
            'text_muted': '#656870',
            'accent': '#6688F0',
            'accent_hover': '#8099F3',
            'accent_light': '#1A1D30',
            'border': '#2D2D30',
            'border_light': '#252528',
            'danger': '#F0656B',
            'favorite': '#F5B830',
            'favorite_light': '#2C2418',
            'pin': '#9E80F8',
            'pin_light': '#221F34',
            'success': '#4DC988',
            'shadow': '#00000040',
            'header_bg': '#161618',
            'overlay': '#88000000',
            'divider': '#2A2A2D',
            'type_text': '#6688F0',
            'type_image': '#4DC988',
            'type_file': '#F5B830',
            'type_folder': '#E8B040',
            'scrollbar': '#3A3A3E',
            'scrollbar_hover': '#505058',
        }
    },
    'sepia': {
        'name': '暖色',
        'colors': {
            'bg_primary': '#FAF6EF',
            'bg_secondary': '#F2ECE0',
            'bg_tertiary': '#E8E0D0',
            'bg_card': '#FFFBF5',
            'bg_card_hover': '#F5EDDC',
            'bg_pinned': '#FCF4E5',
            'bg_input': '#F5EEE2',
            'text_primary': '#43382B',
            'text_secondary': '#756B58',
            'text_muted': '#A09885',
            'accent': '#C07830',
            'accent_hover': '#A06228',
            'accent_light': '#FCF0E0',
            'border': '#D8CFBC',
            'border_light': '#EAE3D3',
            'danger': '#D05050',
            'favorite': '#D49820',
            'favorite_light': '#FCF0D0',
            'pin': '#8B70C8',
            'pin_light': '#F0E8F8',
            'success': '#5A9860',
            'shadow': '#43382B10',
            'header_bg': '#FAF6EF',
            'overlay': '#55433830',
            'divider': '#E8DFCC',
            'type_text': '#C07830',
            'type_image': '#5A9860',
            'type_file': '#D49820',
            'type_folder': '#D8A030',
            'scrollbar': '#D0C8B8',
            'scrollbar_hover': '#B0A898',
        }
    },
    'forest': {
        'name': '森林',
        'colors': {
            'bg_primary': '#F6F9F6',
            'bg_secondary': '#EDF2ED',
            'bg_tertiary': '#DEE8DE',
            'bg_card': '#FFFFFF',
            'bg_card_hover': '#F2F7F2',
            'bg_pinned': '#F0F7F0',
            'bg_input': '#F0F5F0',
            'text_primary': '#1D2D1F',
            'text_secondary': '#506B52',
            'text_muted': '#7D9A7F',
            'accent': '#3D8C40',
            'accent_hover': '#317034',
            'accent_light': '#EDF6ED',
            'border': '#CCDACC',
            'border_light': '#E0EAE0',
            'danger': '#D85050',
            'favorite': '#D49820',
            'favorite_light': '#FCF0D0',
            'pin': '#6A9870',
            'pin_light': '#E8F4E8',
            'success': '#3D8C40',
            'shadow': '#1D2D1F10',
            'header_bg': '#F6F9F6',
            'overlay': '#331D2D1F',
            'divider': '#E0E8E0',
            'type_text': '#3D8C40',
            'type_image': '#508860',
            'type_file': '#D49820',
            'type_folder': '#D8A830',
            'scrollbar': '#BCCCB8',
            'scrollbar_hover': '#90A890',
        }
    },
    'ocean': {
        'name': '海洋',
        'colors': {
            'bg_primary': '#F5F8FB',
            'bg_secondary': '#ECF2F8',
            'bg_tertiary': '#DCE6F2',
            'bg_card': '#FFFFFF',
            'bg_card_hover': '#F2F6FA',
            'bg_pinned': '#F0F5FC',
            'bg_input': '#EEF2F8',
            'text_primary': '#152535',
            'text_secondary': '#455E78',
            'text_muted': '#758FA8',
            'accent': '#2E78C8',
            'accent_hover': '#2565A8',
            'accent_light': '#EDF3FA',
            'border': '#C8D8EC',
            'border_light': '#DEE6F2',
            'danger': '#D84850',
            'favorite': '#D49820',
            'favorite_light': '#FCF0D0',
            'pin': '#5B90C8',
            'pin_light': '#E4F0F8',
            'success': '#3898A0',
            'shadow': '#15253510',
            'header_bg': '#F5F8FB',
            'overlay': '#33152535',
            'divider': '#E0E8F2',
            'type_text': '#2E78C8',
            'type_image': '#3898A0',
            'type_file': '#D49820',
            'type_folder': '#D8A428',
            'scrollbar': '#C0D0E0',
            'scrollbar_hover': '#98B0C8',
        }
    },
}


class ThemeManager:
    """主题管理器"""
    def __init__(self):
        self.current_theme = 'light'
        self.colors = THEMES['light']['colors']

    def apply_theme(self, theme_id: str):
        if theme_id in THEMES:
            self.current_theme = theme_id
            self.colors = THEMES[theme_id]['colors']

    def get_color(self, key: str) -> str:
        return self.colors.get(key, '#000000')

    def get_theme_list(self) -> list:
        return [(tid, t['name']) for tid, t in THEMES.items()]

    def cycle_theme(self) -> str:
        ids = list(THEMES.keys())
        idx = ids.index(self.current_theme)
        nxt = ids[(idx + 1) % len(ids)]
        self.apply_theme(nxt)
        return nxt


theme = ThemeManager()
