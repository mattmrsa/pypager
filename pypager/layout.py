from __future__ import unicode_literals
from prompt_toolkit.enums import SYSTEM_BUFFER
from prompt_toolkit.filters import HasArg, Condition, HasSearch, HasFocus
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, ConditionalContainer, Float, FloatContainer, Container, Align
from prompt_toolkit.layout.controls import BufferControl, TokenListControl
from prompt_toolkit.layout.dimension import Dimension as D
from prompt_toolkit.layout.menus import MultiColumnCompletionsMenu
from prompt_toolkit.layout.processors import Processor, HighlightSelectionProcessor, HighlightSearchProcessor, HighlightMatchingBracketProcessor, TabsProcessor, Transformation, ConditionalProcessor, BeforeInput, MergedProcessor
from prompt_toolkit.layout.lexers import SimpleLexer
from prompt_toolkit.layout.toolbars import SearchToolbar, SystemToolbar, TokenListToolbar
from prompt_toolkit.token import Token

from .filters import HasColon

import weakref

__all__ = (
    'PagerLayout',
)


class _EscapeProcessor(Processor):
    """
    Interpret escape sequences like less/more/most do.
    """
    def __init__(self, source_info):
        self.source_info = source_info

    def apply_transformation(self, ti):
        tokens = self.source_info.line_tokens[ti.lineno]
        return Transformation(tokens[:])


class _Arg(ConditionalContainer):
    def __init__(self):
        def get_tokens(app):
            if app.key_processor.arg is not None:
                return [(Token.Arg, ' %s ' % app.key_processor.arg)]
            else:
                return []

        super(_Arg, self).__init__(
                Window(TokenListControl(get_tokens)),
#, align_right=True)),
                filter=HasArg())


class Titlebar(TokenListToolbar):
    """
    Displayed at the top.
    """
    def __init__(self, pager):
        def get_tokens(app):
            return pager.titlebar_tokens

        super(Titlebar, self).__init__(
            get_tokens,
#            default_char=Char(' ', Token.Titlebar),
            filter=Condition(lambda app: pager.display_titlebar))


class MessageToolbarBar(TokenListToolbar):
    """
    Pop-up (at the bottom) for showing error/status messages.
    """
    def __init__(self, pager):
        def get_tokens(app):
            return [(Token.Message, pager.message)] if pager.message else []

        super(MessageToolbarBar, self).__init__(
            get_tokens,
            filter=Condition(lambda app: bool(pager.message)))


class _DynamicBody(Container):
    def __init__(self, pager):
        self.pager = pager
        self._bodies = weakref.WeakKeyDictionary()  # Map buffer_name to Window.

    def get_buffer_window(self):
        " Return the Container object according to which Buffer/Source is visible. "
        return self.pager.source_info[self.pager.source].window

    def reset(self):
        for body in self._bodies.values():
            body.reset()

    def get_render_info(self):
        return self.get_buffer_window().render_info

    def preferred_width(self, *a, **kw):
        return self.get_buffer_window().preferred_width(*a, **kw)

    def preferred_height(self, *a, **kw):
        return self.get_buffer_window().preferred_height(*a, **kw)

    def write_to_screen(self, *a, **kw):
        return self.get_buffer_window().write_to_screen(*a, **kw)

    def walk(self, *a, **kw):
        # Required for prompt_toolkit.layout.utils.find_window_for_buffer_name.
        return self.get_buffer_window().walk(*a, **kw)


class PagerLayout(object):
    def __init__(self, pager):
        self.pager = pager
        self.dynamic_body = _DynamicBody(pager)

        # Build an interface.
        has_colon = HasColon(pager)

        self.examine_control = BufferControl(
            buffer=pager.examine_buffer,
            lexer=SimpleLexer(token=Token.Toolbar.Examine.Text),
            input_processor=BeforeInput(
                lambda app: [(Token.Toolbar.Examine, ' Examine: ')]),
            )

        self.search_toolbar = SearchToolbar(
            vi_mode=True,
            search_buffer=pager.search_buffer)

        self.container = FloatContainer(
            content=HSplit([
                Titlebar(pager),
                self.dynamic_body,
                self.search_toolbar,
                SystemToolbar(loop=pager.loop),
                ConditionalContainer(
                    content=VSplit([
                            Window(height=D.exact(1),
                                   content=TokenListControl(self._get_statusbar_left_tokens),
                                    token=Token.Statusbar),
                            Window(height=D.exact(1),
                                   content=TokenListControl(self._get_statusbar_right_tokens),
                                   token=Token.Statusbar,
                                   align=Align.RIGHT),
                        ]),
                    filter=~HasSearch() & ~HasFocus(SYSTEM_BUFFER) & ~has_colon & ~HasFocus('EXAMINE')),
                ConditionalContainer(
                    content=TokenListToolbar(
                        lambda app: [(Token.Statusbar, ' :')],
#                        default_char=Char(token=Token.Statusbar)
                    ),
                    filter=has_colon),
                ConditionalContainer(
                    content=Window(
                        self.examine_control,
                        height=D.exact(1),
                        token=Token.Toolbar.Examine),
                    filter=HasFocus(pager.examine_buffer)),
#                ConditionalContainer(
#                    content=Window(
#                        BufferControl(
#                            buffer_name='PATTERN_FILTER',
#                            lexer=SimpleLexer(default_token=Token.Toolbar.Search.Text),
#                            input_processor=BeforeInput(
#                                lambda app: [(Token.Toolbar.Search, '&/')]),
#                            ),
#                        token=Token.Toolbar.Search,
#                        height=D.exact(1)),
#                    filter=HasFocus('PATTERN_FILTER')),
            ]),
            floats=[
                Float(right=0, height=1, bottom=1,
                      content=_Arg()),
                Float(bottom=1, left=0, right=0, height=1,
                      content=MessageToolbarBar(pager)),
                Float(right=0, height=1, bottom=1,
                      content=ConditionalContainer(
                          content=TokenListToolbar(
                              lambda app: [(Token.Loading, ' Loading... ')],
#                              default_char=Char(token=Token.Statusbar)
                          ),
                          filter=Condition(lambda app: pager.current_source_info.waiting_for_input_stream))),
                Float(xcursor=True,
                      ycursor=True,
                      content=MultiColumnCompletionsMenu()),
            ]
        )

#    @property
#    def buffer_window(self):
#        return self.dynamic_body.get_buffer_window()

    def _get_statusbar_left_tokens(self, app):
        """
        Displayed at the bottom left.
        """
        if self.pager.displaying_help:
            message = ' HELP -- Press q when done'
        else:
            message = ' (press h for help or q to quit)'
        return [(Token.Statusbar, message)]

    def _get_statusbar_right_tokens(self, app):
        """
        Displayed at the bottom right.
        """
        buffer = self.pager.source_info[self.pager.source].buffer
        document = buffer.document
        row = document.cursor_position_row + 1
        col = document.cursor_position_col + 1

        if self.pager.source.eof():
            percentage = int(100 * row / document.line_count)
            return [
                (Token.Statusbar.CursorPosition,
                 ' (%s,%s) %s%% ' % (row, col, percentage))]
        else:
            return [
                (Token.Statusbar.CursorPosition,
                 ' (%s,%s) ' % (row, col))]



def create_buffer_window(source_info):
    """
    Window for the main content.
    """
    pager = source_info.pager

    input_processor = MergedProcessor([
        ConditionalProcessor(
            processor=_EscapeProcessor(source_info),
            filter=Condition(lambda app: not bool(source_info.source.lexer)),
        ),
        TabsProcessor(),
        HighlightSelectionProcessor(),
        ConditionalProcessor(
            processor=HighlightSearchProcessor(preview_search=True),
            filter=Condition(lambda app: pager.highlight_search),
        ),
        HighlightMatchingBracketProcessor(),
    ])

    return Window(
        always_hide_cursor=True,
        content=BufferControl(
            buffer=source_info.buffer,
            lexer=source_info.source.lexer,
            input_processor=input_processor,
            search_buffer_control=pager.layout.search_toolbar.control))
