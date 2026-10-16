"""The pet's windows on a Mac, drawn with Cocoa through PyObjC (pip install -r requirements.txt).

Tk can't make see-through windows on current macOS, so the Mac gets its own window code.
All the decisions live in pet.py's Brain; this file only draws and listens to the mouse.
"""
import signal
import webbrowser

import AppKit
import objc
from Foundation import NSData, NSMakeRect, NSObject, NSRunLoop, NSRunLoopCommonModes, NSTimer
from PyObjCTools import AppHelper

from .paths import PACKAGE
from .pet import (HOP, INK, MUTED, PAD, PAPER, SCALE, SIZE, TAIL, TEXT_WIDTH, TICK, Brain, above_pet, beside_pet,
                 bubble_shape, png, review_spot)

FONT, SMALL = AppKit.NSFont.systemFontOfSize_(13), AppKit.NSFont.systemFontOfSize_(10)
ICONS = PACKAGE / "icons" / "macos"
CODE = AppKit.NSFont.monospacedSystemFontOfSize_weight_(11.5, 0)

def color(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, 1.0)

def styled(text, font, hex_color):
    attrs = {AppKit.NSFontAttributeName: font, AppKit.NSForegroundColorAttributeName: color(hex_color)}
    return AppKit.NSAttributedString.alloc().initWithString_attributes_(text, attrs)

def measure(text):
    return text.boundingRectWithSize_options_((TEXT_WIDTH, 10_000), AppKit.NSStringDrawingUsesLineFragmentOrigin).size

def clear_window(w, h, kind=AppKit.NSWindow):
    """A borderless, see-through window that floats above everything, on every desktop."""
    win = kind.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, w, h), AppKit.NSWindowStyleMaskBorderless, AppKit.NSBackingStoreBuffered, False)
    win.setOpaque_(False)
    win.setBackgroundColor_(AppKit.NSColor.clearColor())
    win.setHasShadow_(False)
    win.setLevel_(AppKit.NSFloatingWindowLevel)
    win.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
                               | AppKit.NSWindowCollectionBehaviorStationary)
    win.setReleasedWhenClosed_(False)
    win.setAppearance_(AppKit.NSAppearance.appearanceNamed_(AppKit.NSAppearanceNameAqua))  # light, like the cream panels
    return win

def native_panel(w, h):
    """A rounded, see-through panel that looks like a macOS popover and follows light/dark mode.
    Returns the window and a top-down view to put things in."""
    win = clear_window(w, h, KeyWindow)
    win.setAppearance_(None)  # unlike the pet and its bubble, the chat follows the system look
    win.setHasShadow_(True)
    blur = AppKit.NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
    blur.setMaterial_(AppKit.NSVisualEffectMaterialPopover)
    blur.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
    blur.setState_(AppKit.NSVisualEffectStateActive)
    blur.setWantsLayer_(True)
    blur.layer().setCornerRadius_(12)
    blur.layer().setMasksToBounds_(True)
    inside = FlippedView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
    blur.addSubview_(inside)
    win.setContentView_(blur)
    return win, inside

def edit_menu():
    """The standard Edit menu. Gemlin shows no menu bar of its own, but on a Mac the ⌘V / ⌘C / ⌘X / ⌘A
    shortcuts only reach a text box through this menu: without it, pasting into the chat does nothing."""
    bar, edit = AppKit.NSMenu.alloc().init(), AppKit.NSMenu.alloc().initWithTitle_("Edit")
    for entry in (("Undo", "undo:", "z"), ("Redo", "redo:", "Z"), None, ("Cut", "cut:", "x"), ("Copy", "copy:", "c"),
                  ("Paste", "paste:", "v"), ("Select All", "selectAll:", "a")):
        if entry is None:
            edit.addItem_(AppKit.NSMenuItem.separatorItem())
        else:
            edit.addItemWithTitle_action_keyEquivalent_(*entry)  # no target: goes to whatever has the cursor
    for title, submenu in (("Gemlin", AppKit.NSMenu.alloc().initWithTitle_("Gemlin")), ("Edit", edit)):
        bar.addItemWithTitle_action_keyEquivalent_(title, None, "").setSubmenu_(submenu)
    return bar

def menu_bar_icon():
    """Gemlin's menu bar mark. As a template image, macOS colors it to match the menu bar."""
    image = AppKit.NSImage.alloc().initWithSize_((18, 18))
    for name in ("GemlinTemplate.png", "GemlinTemplate@2x.png"):
        rep = AppKit.NSImageRep.imageRepWithContentsOfFile_(str(ICONS / name))
        if rep:
            rep.setSize_((18, 18))
            image.addRepresentation_(rep)
    image.setTemplate_(True)
    return image

def label(text, size=12, secondary=False, bold=False):
    field = AppKit.NSTextField.labelWithString_(text)
    field.setFont_(AppKit.NSFont.boldSystemFontOfSize_(size) if bold else AppKit.NSFont.systemFontOfSize_(size))
    if secondary:
        field.setTextColor_(AppKit.NSColor.secondaryLabelColor())
    return field

SHORTCUTS = {"v": "paste:", "c": "copy:", "x": "cut:", "a": "selectAll:", "z": "undo:", "Z": "redo:"}

class KeyWindow(AppKit.NSWindow):  # borderless windows can't take typing unless they say so
    def canBecomeKeyWindow(self):
        return True

    def performKeyEquivalent_(self, event):
        # ⌘V / ⌘C / ⌘X / ⌘A / ⌘Z straight to the text box. The Edit menu should do this, but a menu
        # bar app doesn't always get its menu's shortcuts, and then pasting silently did nothing.
        flags = event.modifierFlags() & AppKit.NSEventModifierFlagDeviceIndependentFlagsMask
        if flags & AppKit.NSEventModifierFlagCommand and not flags & (AppKit.NSEventModifierFlagControl
                                                                      | AppKit.NSEventModifierFlagOption):
            action = SHORTCUTS.get(event.charactersIgnoringModifiers() or "")
            if action and AppKit.NSApp.sendAction_to_from_(action, None, self):
                return True
        return objc.super(KeyWindow, self).performKeyEquivalent_(event)

class FlippedView(AppKit.NSView):  # y points down, like everywhere else in Gemlin
    def isFlipped(self):
        return True

    def acceptsFirstMouse_(self, event):
        return True

class PetView(FlippedView):
    def drawRect_(self, rect):
        if self.image:
            AppKit.NSGraphicsContext.currentContext().setImageInterpolation_(AppKit.NSImageInterpolationNone)
            self.image.drawInRect_fromRect_operation_fraction_respectFlipped_hints_(
                NSMakeRect(0, HOP - self.lift, SIZE, SIZE), AppKit.NSZeroRect,
                AppKit.NSCompositingOperationSourceOver, 1.0, True, None)

    def mouseDown_(self, event):
        self.owner.mouse("down")

    def mouseDragged_(self, event):
        self.owner.mouse("drag")

    def mouseUp_(self, event):
        self.owner.mouse("up")

class BubbleView(FlippedView):
    def drawRect_(self, rect):
        w, h = self.size
        path = AppKit.NSBezierPath.bezierPath()
        first, *rest = bubble_shape(w, h)
        path.moveToPoint_(first)
        for point in rest:
            path.lineToPoint_(point)
        path.closePath()
        color(PAPER).setFill()
        path.fill()
        color(INK).setStroke()
        path.setLineWidth_(2)
        path.stroke()
        self.text.drawWithRect_options_(NSMakeRect(PAD + 2, PAD - 2, TEXT_WIDTH, h),
                                        AppKit.NSStringDrawingUsesLineFragmentOrigin)
        if self.footer:
            width = self.footer.size().width
            self.footer.drawAtPoint_((w - PAD - width, h - PAD - 6))

    def mouseDown_(self, event):
        self.owner.brain.bubble_clicked()

class MacPet(NSObject):
    @objc.python_method
    def setup(self, me, follow):
        screen = AppKit.NSScreen.screens()[0]
        whole, usable = screen.frame(), screen.visibleFrame()
        self.top = whole.size.height  # Cocoa counts y up from the bottom; Brain counts down from the top
        self.brain = Brain(me, int(whole.size.width), int(self.top - usable.origin.y), follow)
        self.images, self.shown, self.chat, self.review, self.look_version, self.attention = {}, None, None, None, 0, 0
        self.win = clear_window(SIZE, SIZE + HOP)
        self.view = PetView.alloc().initWithFrame_(NSMakeRect(0, 0, SIZE, SIZE + HOP))
        self.view.owner, self.view.image, self.view.lift = self, None, 0
        self.win.setContentView_(self.view)
        self.bubble_win = clear_window(10, 10)
        self.bubble = BubbleView.alloc().initWithFrame_(NSMakeRect(0, 0, 10, 10))
        self.bubble.owner, self.bubble.size = self, (10, 10)  # drawRect_ can run before the first bubble
        self.bubble.text, self.bubble.footer = styled("", FONT, INK), None
        self.bubble_win.setContentView_(self.bubble)
        AppKit.NSApp.setApplicationIconImage_(AppKit.NSImage.alloc().initWithContentsOfFile_(str(ICONS / "Gemlin.icns")))
        self.menu = AppKit.NSMenu.alloc().init()
        self.menu.setDelegate_(self)  # rebuilt each time it opens, so checkmarks are current
        self.view.setMenu_(self.menu)  # right-click or control-click on Gemlin
        self.status = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(AppKit.NSVariableStatusItemLength)
        self.status.button().setImage_(menu_bar_icon())
        self.status.button().setToolTip_(me["name"])
        self.bar_menu = AppKit.NSMenu.alloc().init()
        self.bar_menu.setDelegate_(self)
        self.status.setMenu_(self.bar_menu)  # the same menu, in the menu bar
        self.tick_(None)
        self.win.orderFrontRegardless()
        timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(TICK / 1000, self, "tick:", None, True)
        NSRunLoop.currentRunLoop().addTimer_forMode_(timer, NSRunLoopCommonModes)  # keeps going while dragging

    @objc.python_method
    def place(self, win, x, y):
        win.setFrameOrigin_((x, self.top - y - win.frame().size.height))

    @objc.python_method
    def mouse(self, what):
        where = AppKit.NSEvent.mouseLocation()
        x, y = where.x, self.top - where.y
        if what == "down":
            self.brain.pick_up(x, y)
        elif what == "drag":
            self.brain.drag(x, y)
        else:
            self.brain.drop()

    def tick_(self, timer):
        b = self.brain
        b.step()
        if b.done:
            AppKit.NSApp.terminate_(None)
            return
        if b.attention != self.attention:  # you opened the Gemlin app or picked Chat: come to the front
            self.attention = b.attention
            self.sync_chat()
            for win in (self.win, self.bubble_win):
                win.orderFrontRegardless()
            if self.chat:
                self.focus(self.chat, self.chat_field)
        if b.look_version != self.look_version:  # new look: rebuild the sprites
            self.images, self.look_version = {}, b.look_version
        if b.frame not in self.images:
            data = png(b.art.frame(*b.frame), scale=SCALE * 2)  # extra pixels keep it crisp on Retina screens
            image = AppKit.NSImage.alloc().initWithData_(NSData.dataWithBytes_length_(data, len(data)))
            image.setSize_((SIZE, SIZE))
            self.images[b.frame] = image
        if (self.view.image, self.view.lift) != (self.images[b.frame], b.lift):
            self.view.image, self.view.lift = self.images[b.frame], b.lift
            self.view.setNeedsDisplay_(True)
        self.place(self.win, b.x, b.y)
        self.sync_bubble(b.bubble)
        self.sync_chat()
        self.sync_review()

    @objc.python_method
    def sync_bubble(self, want):
        if want != self.shown:
            self.shown = want
            if not want:
                self.bubble_win.orderOut_(None)
                return
            text, footer = want
            self.bubble.text = styled(text, FONT, INK)
            self.bubble.footer = styled(footer, SMALL, MUTED) if footer else None
            size = measure(self.bubble.text)
            w, h = max(int(size.width) + 2 * PAD + 6, 70), int(size.height) + 2 * PAD - 2 + (14 if footer else 0)
            self.bubble.size = (w, h)
            self.bubble_win.setContentSize_((w, h + TAIL))
            self.bubble.setFrame_(NSMakeRect(0, 0, w, h + TAIL))
            self.bubble.setNeedsDisplay_(True)
            self.bubble_win.orderFrontRegardless()
        if want:
            self.place(self.bubble_win, *above_pet(self.brain, *self.bubble.size))

    @objc.python_method
    def focus(self, win, view):  # take the keyboard so you can type straight away
        app = AppKit.NSApp
        app.activate() if hasattr(app, "activate") else app.activateIgnoringOtherApps_(True)
        win.makeKeyAndOrderFront_(None)
        win.makeFirstResponder_(view)

    @objc.python_method
    def sync_chat(self):
        b = self.brain
        mode = (b.needs_key, b.button, b.me["name"])
        if self.chat and (not b.chatting or mode != self.chat_mode):
            self.chat.orderOut_(None)
            self.chat = None
            if not b.chatting and hasattr(AppKit.NSApp, "deactivate"):
                AppKit.NSApp.deactivate()  # hand the keyboard back to what you were doing
        if b.chatting and not self.chat:
            w, h = 300, 88
            self.chat, view = native_panel(w, h)
            self.chat_mode = mode
            view.addSubview_(title := label("Paste your API key" if b.needs_key else f"Chat with {b.me['name']}", bold=True))
            title.setFrame_(NSMakeRect(14, 10, w - 28, 16))
            field = (AppKit.NSSecureTextField if b.needs_key else AppKit.NSTextField).alloc().initWithFrame_(
                NSMakeRect(14, 31, w - 28, 24))
            field.setBezelStyle_(AppKit.NSTextFieldRoundedBezel)
            field.setPlaceholderString_("AIza…" if b.needs_key else "Say something…")
            field.setTarget_(self)
            field.setAction_("send:")
            field.setDelegate_(self)
            view.addSubview_(field)
            view.addSubview_(hint := label("Enter to send · Esc to close", size=10.5, secondary=True))
            hint.setFrame_(NSMakeRect(14, 63, 170, 14))
            button = AppKit.NSButton.buttonWithTitle_target_action_(b.button[0], self, "openLink:")
            button.setControlSize_(AppKit.NSControlSizeSmall)
            button.setFont_(AppKit.NSFont.systemFontOfSize_(11))
            button.sizeToFit()
            bw = button.frame().size.width
            button.setFrame_(NSMakeRect(w - 14 - bw, 59, bw, 22))
            view.addSubview_(button)
            self.chat_field = field
            if not self.review:
                self.focus(self.chat, field)
        if self.chat:  # it follows the pet around, even while you drag it
            self.place(self.chat, *beside_pet(b, 300, 88))

    @objc.python_method
    def sync_review(self):
        asking = self.brain.asking
        if self.review and (not asking or asking["id"] != self.review_id):
            self.review.orderOut_(None)
            self.review = None
            if self.chat:
                self.focus(self.chat, self.chat_field)
        if asking and not self.review:
            code = asking["code"]
            w = 560 if code else 340
            question = AppKit.NSTextField.wrappingLabelWithString_(asking["question"])
            question.setFont_(FONT)
            question.setPreferredMaxLayoutWidth_(w - 32)
            qh = question.fittingSize().height
            ch = min(340, 18 + 15 * (code.count("\n") + 1)) if code else 0
            h = 18 + qh + (12 + ch if code else 0) + 54
            self.review, view = native_panel(w, h)
            self.review_id = asking["id"]
            question.setFrame_(NSMakeRect(16, 16, w - 32, qh))
            view.addSubview_(question)
            if code:
                scroll = AppKit.NSScrollView.alloc().initWithFrame_(NSMakeRect(16, 18 + qh + 10, w - 32, ch))
                scroll.setHasVerticalScroller_(True)
                scroll.setHasHorizontalScroller_(True)
                scroll.setBorderType_(AppKit.NSBezelBorder)
                text = AppKit.NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, w - 36, ch))
                text.setHorizontallyResizable_(True)  # long lines scroll sideways instead of wrapping
                text.textContainer().setWidthTracksTextView_(False)
                text.textContainer().setContainerSize_((10_000, 10_000_000))
                text.setEditable_(False)
                text.setFont_(CODE)
                text.setString_(code)
                scroll.setDocumentView_(text)
                view.addSubview_(scroll)
            no = AppKit.NSButton.buttonWithTitle_target_action_("No", self, "answerNo:")
            no.setKeyEquivalent_("\x1b")  # Esc means no. Yes needs a click, so nothing gets approved by accident
            yes = AppKit.NSButton.buttonWithTitle_target_action_("Yes, install it" if code else "Yes", self, "answerYes:")
            right = w - 16
            for button in (yes, no):  # right to left: Yes, then No
                button.sizeToFit()
                bw = button.frame().size.width + 16
                button.setFrame_(NSMakeRect(right - bw, h - 44, bw, 30))
                view.addSubview_(button)
                right -= bw + 8
            self.place(self.review, *review_spot(self.brain, w, h))
            self.focus(self.review, no)

    def answerYes_(self, button):
        self.brain.answer(True)

    def answerNo_(self, button):
        self.brain.answer(False)

    def send_(self, field):
        self.brain.heard(field.stringValue())
        field.setStringValue_("")

    @objc.typedSelector(b"Z@:@@:")
    def control_textView_doCommandBySelector_(self, control, view, command):
        if "cancelOperation" in str(command):  # Esc
            self.brain.chatting = False
            return True
        return False

    def menuNeedsUpdate_(self, menu):  # just before a menu opens: fill it from the Brain's menu
        menu.removeAllItems()
        if menu is self.bar_menu:
            heading = menu.addItemWithTitle_action_keyEquivalent_(self.brain.me["name"], None, "")
            heading.setEnabled_(False)
        for entry in self.brain.menu():
            if entry is None:
                menu.addItem_(AppKit.NSMenuItem.separatorItem())
                continue
            title, action, checked = entry
            item = menu.addItemWithTitle_action_keyEquivalent_(title, "menuItem:", "")
            item.setTarget_(self)
            item.setRepresentedObject_(action)
            if checked is not None:
                item.setState_(AppKit.NSControlStateValueOn if checked else AppKit.NSControlStateValueOff)

    def menuItem_(self, item):
        if page := self.brain.menu_action(item.representedObject()):
            webbrowser.open(page)

    def openLink_(self, button):  # "Get a free key" or "Customize me"
        webbrowser.open(self.brain.button_clicked())

def run(me, follow):
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)  # no Dock icon
    app.setMainMenu_(edit_menu())  # so ⌘V pastes into the chat
    pet = MacPet.alloc().init()
    pet.setup(me, follow)
    if follow:  # Ctrl+C is for gemlin.py; we leave when it does
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    AppHelper.runEventLoop(installInterrupt=not follow)
