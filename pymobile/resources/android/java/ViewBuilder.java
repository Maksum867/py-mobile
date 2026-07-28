package org.pymobile.app;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.CompoundButton;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * Turns a serialised PyMobile widget tree into a native Android view hierarchy.
 *
 * The mapping is intentionally direct — one widget type to one Android view —
 * so behaviour is predictable and new widgets are cheap to add.
 */
final class ViewBuilder {

    /** Density scale, used to convert the framework's dp values to pixels. */
    private final float density;
    private final Context context;

    ViewBuilder(Context context) {
        this.context = context;
        this.density = context.getResources().getDisplayMetrics().density;
    }

    private int dp(int value) {
        return Math.round(value * density);
    }

    /** Build a child defensively: a failure must not hide the whole screen. */
    private View buildChild(JSONObject node) {
        try {
            return build(node);
        } catch (Exception error) {
            android.util.Log.e("pymobile", "widget failed: " + node.optString("type"), error);
            TextView fallback = new TextView(context);
            fallback.setText("[" + node.optString("type") + ": " + error + "]");
            fallback.setTextColor(Color.parseColor("#C62828"));
            return fallback;
        }
    }

    /** Build the view for one node, recursing into children. */
    View build(JSONObject node) throws JSONException {
        String type = node.optString("type", "Label");
        JSONObject props = node.optJSONObject("props");
        if (props == null) {
            props = new JSONObject();
        }
        JSONObject style = node.optJSONObject("style");
        String id = node.optString("id", "");
        boolean enabled = node.optBoolean("enabled", true);
        boolean visible = node.optBoolean("visible", true);

        View view;
        switch (type) {
            case "Column":
                view = buildLinear(node, props, LinearLayout.VERTICAL);
                break;
            case "Row":
                view = buildLinear(node, props, LinearLayout.HORIZONTAL);
                break;
            case "ScrollView":
                view = buildScroll(node, props);
                break;
            case "Stack":
                view = buildStack(node);
                break;
            case "Button":
                view = buildButton(id, props);
                break;
            case "TextInput":
                view = buildTextInput(id, props);
                break;
            case "Switch":
                view = buildSwitch(id, props);
                break;
            case "ProgressBar":
                view = buildProgress(props);
                break;
            case "Image":
                view = buildImage(props);
                break;
            case "Spacer":
                view = buildSpacer(props);
                break;
            case "Label":
            default:
                view = buildLabel(props);
                break;
        }

        view.setEnabled(enabled);
        view.setVisibility(visible ? View.VISIBLE : View.GONE);
        applyStyle(view, style);
        // Remember the widget id so a later tree can patch this view in place
        // instead of rebuilding the screen (which loses scroll and focus).
        view.setTag(id);
        return view;
    }

    // -- containers -------------------------------------------------------

    private View buildLinear(JSONObject node, JSONObject props, int orientation)
            throws JSONException {
        LinearLayout layout = new LinearLayout(context);
        layout.setOrientation(orientation);

        String align = props.optString("align", "start");
        if (orientation == LinearLayout.VERTICAL) {
            layout.setGravity(horizontalGravity(align));
        } else {
            layout.setGravity(Gravity.CENTER_VERTICAL | horizontalGravity(align));
        }

        int spacing = dp(props.optInt("spacing", 0));
        JSONArray children = node.optJSONArray("children");
        if (children != null) {
            for (int i = 0; i < children.length(); i++) {
                JSONObject childNode = children.getJSONObject(i);
                View child = buildChild(childNode);
                int width = orientation == LinearLayout.VERTICAL
                        ? ViewGroup.LayoutParams.MATCH_PARENT
                        : ViewGroup.LayoutParams.WRAP_CONTENT;
                int height = ViewGroup.LayoutParams.WRAP_CONTENT;
                if ("Spacer".equals(childNode.optString("type"))) {
                    JSONObject spacerProps = childNode.optJSONObject("props");
                    int size = dp(spacerProps == null ? 8 : spacerProps.optInt("size", 8));
                    if (orientation == LinearLayout.VERTICAL) {
                        height = size;
                    } else {
                        width = size;
                    }
                }
                LinearLayout.LayoutParams params =
                        new LinearLayout.LayoutParams(width, height);
                if (spacing > 0 && i > 0) {
                    if (orientation == LinearLayout.VERTICAL) {
                        params.topMargin = spacing;
                    } else {
                        params.leftMargin = spacing;
                    }
                }
                layout.addView(child, params);
            }
        }
        return layout;
    }

    private int horizontalGravity(String align) {
        if ("center".equals(align)) {
            return Gravity.CENTER_HORIZONTAL;
        }
        if ("end".equals(align)) {
            return Gravity.END;
        }
        return Gravity.START;
    }

    private View buildScroll(JSONObject node, JSONObject props) throws JSONException {
        boolean horizontal = props.optBoolean("horizontal", false);
        // setFillViewport lives on each concrete class, not on ViewGroup.
        ViewGroup scroller;
        if (horizontal) {
            HorizontalScrollView view = new HorizontalScrollView(context);
            view.setFillViewport(true);
            scroller = view;
        } else {
            ScrollView view = new ScrollView(context);
            view.setFillViewport(true);
            scroller = view;
        }

        LinearLayout content = new LinearLayout(context);
        content.setOrientation(horizontal ? LinearLayout.HORIZONTAL : LinearLayout.VERTICAL);
        JSONArray children = node.optJSONArray("children");
        if (children != null) {
            for (int i = 0; i < children.length(); i++) {
                content.addView(buildChild(children.getJSONObject(i)),
                        new LinearLayout.LayoutParams(
                                ViewGroup.LayoutParams.MATCH_PARENT,
                                ViewGroup.LayoutParams.WRAP_CONTENT));
            }
        }
        scroller.addView(content, new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return scroller;
    }

    private View buildStack(JSONObject node) throws JSONException {
        android.widget.FrameLayout frame = new android.widget.FrameLayout(context);
        JSONArray children = node.optJSONArray("children");
        if (children != null) {
            for (int i = 0; i < children.length(); i++) {
                frame.addView(buildChild(children.getJSONObject(i)));
            }
        }
        return frame;
    }

    // -- leaves -----------------------------------------------------------

    private View buildLabel(JSONObject props) {
        TextView label = new TextView(context);
        label.setText(props.optString("text", ""));
        label.setTextColor(Color.parseColor("#212121"));
        label.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        return label;
    }

    private View buildButton(final String id, JSONObject props) {
        Button button = new Button(context);
        button.setText(props.optString("text", ""));
        button.setAllCaps(false);
        button.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Native.dispatchEvent(id, "press", "");
            }
        });
        return button;
    }

    private View buildTextInput(final String id, JSONObject props) {
        EditText input = new EditText(context);
        input.setText(props.optString("value", ""));
        input.setHint(props.optString("placeholder", ""));
        if (props.optBoolean("multiline", false)) {
            input.setInputType(InputType.TYPE_CLASS_TEXT
                    | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
            input.setMinLines(3);
        } else if (props.optBoolean("password", false)) {
            input.setInputType(InputType.TYPE_CLASS_TEXT
                    | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        } else {
            input.setInputType(InputType.TYPE_CLASS_TEXT);
            input.setSingleLine(true);
        }
        input.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int a, int b, int c) {
            }

            @Override
            public void onTextChanged(CharSequence s, int a, int b, int c) {
            }

            @Override
            public void afterTextChanged(Editable editable) {
                Native.dispatchEvent(id, "change", editable.toString());
            }
        });
        return input;
    }

    private View buildSwitch(final String id, JSONObject props) {
        Switch toggle = new Switch(context);
        toggle.setChecked(props.optBoolean("checked", false));
        toggle.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(CompoundButton view, boolean checked) {
                Native.dispatchEvent(id, "toggle", checked ? "true" : "false");
            }
        });
        return toggle;
    }

    private View buildProgress(JSONObject props) {
        boolean indeterminate = props.optBoolean("indeterminate", false);
        ProgressBar bar = new ProgressBar(
                context, null,
                indeterminate ? android.R.attr.progressBarStyle
                              : android.R.attr.progressBarStyleHorizontal);
        bar.setIndeterminate(indeterminate);
        if (!indeterminate) {
            int maximum = (int) props.optDouble("maximum", 100);
            bar.setMax(Math.max(1, maximum));
            bar.setProgress((int) props.optDouble("value", 0));
        }
        return bar;
    }

    private View buildImage(JSONObject props) {
        ImageView image = new ImageView(context);
        String source = props.optString("source", "");
        image.setScaleType("cover".equals(props.optString("fit", "contain"))
                ? ImageView.ScaleType.CENTER_CROP
                : ImageView.ScaleType.FIT_CENTER);
        try {
            java.io.File file = new java.io.File(source);
            if (!file.isAbsolute()) {
                file = new java.io.File(context.getFilesDir(), "pymobile/app/" + source);
            }
            if (file.exists()) {
                image.setImageBitmap(
                        android.graphics.BitmapFactory.decodeFile(file.getAbsolutePath()));
            }
        } catch (RuntimeException ignored) {
            // A broken image must not take the whole screen down.
        }
        return image;
    }

    private View buildSpacer(JSONObject props) {
        // No setLayoutParams here: the parent container assigns params of its
        // own type. A bare ViewGroup.LayoutParams would make LinearLayout throw
        // ClassCastException and silently drop the rest of the tree.
        View spacer = new View(context);
        spacer.setMinimumWidth(dp(props.optInt("size", 8)));
        spacer.setMinimumHeight(dp(props.optInt("size", 8)));
        return spacer;
    }

    /**
     * Apply a new tree to an existing hierarchy without recreating views.
     *
     * Rebuilding on every render reset the scroll position and closed the
     * keyboard after each keystroke. Updating in place keeps both, and is also
     * far cheaper. Returns false when the structure changed and a full rebuild
     * is required.
     */
    boolean update(View view, JSONObject node) {
        try {
            return updateNode(view, node);
        } catch (JSONException error) {
            return false;
        }
    }

    private boolean updateNode(View view, JSONObject node) throws JSONException {
        String type = node.optString("type", "Label");
        String id = node.optString("id", "");
        if (view == null || !id.equals(view.getTag())) {
            return false;
        }

        JSONObject props = node.optJSONObject("props");
        if (props == null) {
            props = new JSONObject();
        }

        view.setEnabled(node.optBoolean("enabled", true));
        view.setVisibility(node.optBoolean("visible", true) ? View.VISIBLE : View.GONE);

        if (view instanceof ViewGroup) {
            JSONArray children = node.optJSONArray("children");
            ViewGroup group = (ViewGroup) view;
            ViewGroup target = group;
            // ScrollView wraps its content in a LinearLayout.
            if ((group instanceof ScrollView || group instanceof HorizontalScrollView)
                    && group.getChildCount() == 1
                    && group.getChildAt(0) instanceof ViewGroup) {
                target = (ViewGroup) group.getChildAt(0);
            }
            int count = children == null ? 0 : children.length();
            if (target.getChildCount() != count) {
                return false;
            }
            for (int i = 0; i < count; i++) {
                if (!updateNode(target.getChildAt(i), children.getJSONObject(i))) {
                    return false;
                }
            }
            return true;
        }

        if (view instanceof Button) {
            ((Button) view).setText(props.optString("text", ""));
            return true;
        }
        if (view instanceof Switch) {
            Switch toggle = (Switch) view;
            boolean checked = props.optBoolean("checked", false);
            if (toggle.isChecked() != checked) {
                toggle.setChecked(checked);
            }
            return true;
        }
        if (view instanceof EditText) {
            // Never write back into a focused field: it would move the caret
            // and dismiss the keyboard mid-typing.
            EditText input = (EditText) view;
            String value = props.optString("value", "");
            if (!input.hasFocus() && !value.contentEquals(input.getText())) {
                input.setText(value);
            }
            return true;
        }
        if (view instanceof ProgressBar) {
            ProgressBar bar = (ProgressBar) view;
            if (!bar.isIndeterminate()) {
                bar.setProgress((int) props.optDouble("value", 0));
            }
            return true;
        }
        if (view instanceof TextView) {
            ((TextView) view).setText(props.optString("text", ""));
            return true;
        }
        return true;
    }

    // -- styling ----------------------------------------------------------

    private void applyStyle(View view, JSONObject style) {
        if (style == null) {
            return;
        }
        if (view instanceof TextView) {
            TextView text = (TextView) view;
            if (style.has("color")) {
                text.setTextColor(parseColor(style.optString("color"), Color.BLACK));
            }
            if (style.has("font_size")) {
                text.setTextSize(TypedValue.COMPLEX_UNIT_SP, (float) style.optDouble("font_size"));
            }
            boolean bold = style.optBoolean("bold", false);
            boolean italic = style.optBoolean("italic", false);
            if (bold || italic) {
                int flags = (bold ? Typeface.BOLD : 0) | (italic ? Typeface.ITALIC : 0);
                text.setTypeface(text.getTypeface(), flags);
            }
            String align = style.optString("align", "");
            if ("center".equals(align)) {
                text.setGravity(Gravity.CENTER);
            }
        }

        JSONArray padding = style.optJSONArray("padding");
        if (padding != null && padding.length() == 4) {
            view.setPadding(dp(padding.optInt(0)), dp(padding.optInt(1)),
                    dp(padding.optInt(2)), dp(padding.optInt(3)));
        }

        if (style.has("background") || style.has("corner_radius")) {
            GradientDrawable shape = new GradientDrawable();
            shape.setColor(parseColor(style.optString("background", "#00000000"),
                    Color.TRANSPARENT));
            shape.setCornerRadius(dp(style.optInt("corner_radius", 0)));
            view.setBackground(shape);
        }

        JSONArray margin = style.optJSONArray("margin");
        if (margin != null && margin.length() == 4) {
            ViewGroup.LayoutParams params = view.getLayoutParams();
            if (params instanceof ViewGroup.MarginLayoutParams) {
                ((ViewGroup.MarginLayoutParams) params).setMargins(
                        dp(margin.optInt(0)), dp(margin.optInt(1)),
                        dp(margin.optInt(2)), dp(margin.optInt(3)));
            }
        }
    }

    /** Parse #RGB / #RRGGBB / #AARRGGBB, falling back on anything unexpected. */
    private int parseColor(String value, int fallback) {
        if (value == null || value.isEmpty()) {
            return fallback;
        }
        try {
            return Color.parseColor(value);
        } catch (IllegalArgumentException error) {
            return fallback;
        }
    }
}
