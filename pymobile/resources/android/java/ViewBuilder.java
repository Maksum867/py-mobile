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
import android.view.HapticFeedbackConstants;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.CompoundButton;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.RatingBar;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Spinner;
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
            case "Grid":
                view = buildGrid(node, props);
                break;
            case "SafeArea":
                view = buildSafeArea(node, props);
                break;
            case "Expanded":
            case "Flexible":
                view = buildFlex(node);
                break;
            case "Divider":
                view = buildDivider(props);
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
            case "Checkbox":
                view = buildCheckbox(id, props);
                break;
            case "Slider":
                view = buildSlider(id, props);
                break;
            case "RatingBar":
                view = buildRatingBar(id, props);
                break;
            case "Dropdown":
                view = buildDropdown(id, props);
                break;
            case "Chip":
                view = buildChip(id, props);
                break;
            case "Badge":
                view = buildBadge(props);
                break;
            case "SearchBar":
                view = buildTextInput(id, props);
                break;
            case "Stepper":
                view = buildStepper(id, props);
                break;
            case "RadioButton":
                view = buildRadioButton(id, props);
                break;
            case "RadioGroup":
                view = buildRadioGroup(node, id, props);
                break;
            case "SegmentedButtons":
                view = buildSegmented(id, props);
                break;
            case "Link":
                view = buildLink(id, props);
                break;
            case "ProgressText":
                view = buildProgressText(id, props);
                break;
            case "DataTable":
                view = buildDataTable(node, props);
                break;
            case "Avatar":
                view = buildAvatar(props);
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
            case "List":
                view = buildList(node, props);
                break;
            case "ListTile":
                view = buildListTile(id, props);
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
        // cross_align is optional: without it the historical defaults apply
        // (children stretch in a Column, sit centred in a Row).
        String crossAlign = props.optString("cross_align", "");
        layout.setGravity(gravityFor(orientation, align, crossAlign));

        int spacing = dp(props.optInt("spacing", 0));
        JSONArray children = node.optJSONArray("children");
        if (children != null) {
            for (int i = 0; i < children.length(); i++) {
                JSONObject childNode = children.getJSONObject(i);
                View child = buildChild(childNode);
                LinearLayout.LayoutParams params =
                        childParams(childNode, orientation, crossAlign);
                if (spacing > 0 && i > 0) {
                    if (orientation == LinearLayout.VERTICAL) {
                        params.topMargin += spacing;
                    } else {
                        params.leftMargin += spacing;
                    }
                }
                layout.addView(child, params);
            }
        }
        return layout;
    }

    /**
     * Layout params for one child of a Row/Column.
     *
     * Three things are decided here, all of which used to be impossible to
     * express from Python: the flex share claimed by Expanded/Flexible, the
     * explicit size of a Spacer, and how the child is sized across the axis.
     */
    private LinearLayout.LayoutParams childParams(
            JSONObject childNode, int orientation, String crossAlign) {
        String type = childNode.optString("type");
        JSONObject childProps = childNode.optJSONObject("props");
        if (childProps == null) {
            childProps = new JSONObject();
        }
        boolean vertical = orientation == LinearLayout.VERTICAL;

        boolean stretch = crossAlign.isEmpty() ? vertical : "stretch".equals(crossAlign);
        int across = stretch
                ? ViewGroup.LayoutParams.MATCH_PARENT
                : ViewGroup.LayoutParams.WRAP_CONTENT;
        int width = vertical ? across : ViewGroup.LayoutParams.WRAP_CONTENT;
        int height = vertical ? ViewGroup.LayoutParams.WRAP_CONTENT : across;

        // Expanded/Flexible: hand the child a weighted share of the free space.
        // A tight fit needs a zero base size, otherwise the child's own
        // measurement is added on top of its share and the split is uneven.
        if ("Expanded".equals(type) || "Flexible".equals(type)) {
            int flex = Math.max(1, childProps.optInt("flex", 1));
            boolean tight = !"loose".equals(childProps.optString("fit", "tight"));
            if (vertical) {
                height = tight ? 0 : ViewGroup.LayoutParams.WRAP_CONTENT;
            } else {
                width = tight ? 0 : ViewGroup.LayoutParams.WRAP_CONTENT;
            }
            LinearLayout.LayoutParams flexParams =
                    new LinearLayout.LayoutParams(width, height, flex);
            applyCrossGravity(flexParams, orientation, crossAlign);
            return flexParams;
        }

        if ("Spacer".equals(type)) {
            int size = dp(childProps.optInt("size", 8));
            if (vertical) {
                height = size;
            } else {
                width = size;
            }
        }

        if ("Divider".equals(type)) {
            // A divider spans the container across the axis and is exactly as
            // thick as it says on the main axis.
            int thickness = dp(Math.max(1, childProps.optInt("thickness", 1)));
            if (childProps.optBoolean("vertical", false)) {
                width = thickness;
                height = vertical ? dp(24) : ViewGroup.LayoutParams.MATCH_PARENT;
            } else {
                width = vertical ? ViewGroup.LayoutParams.MATCH_PARENT : dp(24);
                height = thickness;
            }
            int inset = dp(childProps.optInt("inset", 0));
            LinearLayout.LayoutParams dividerParams =
                    new LinearLayout.LayoutParams(width, height);
            if (childProps.optBoolean("vertical", false)) {
                dividerParams.topMargin = inset;
                dividerParams.bottomMargin = inset;
            } else {
                dividerParams.leftMargin = inset;
                dividerParams.rightMargin = inset;
            }
            return dividerParams;
        }

        // An explicit weight in the style keeps working exactly as before.
        JSONObject style = childNode.optJSONObject("style");
        float weight = style == null ? 0f : (float) style.optDouble("weight", 0);
        LinearLayout.LayoutParams params = weight > 0
                ? new LinearLayout.LayoutParams(
                        vertical ? width : 0, vertical ? 0 : height, weight)
                : new LinearLayout.LayoutParams(width, height);
        applyCrossGravity(params, orientation, crossAlign);
        applyBoxStyle(params, style);
        return params;
    }

    /**
     * Apply the parts of a Style that live on the layout params, not the view.
     *
     * margin, width and height cannot be set in applyStyle(): that runs while
     * the view is still detached, so getLayoutParams() is null and the values
     * were silently dropped. They belong here, where the params are created.
     */
    private void applyBoxStyle(ViewGroup.MarginLayoutParams params, JSONObject style) {
        if (style == null) {
            return;
        }
        applyMargin(params, style);

        int width = dimension(style, "width");
        if (width != Integer.MIN_VALUE) {
            params.width = width;
        }
        int height = dimension(style, "height");
        if (height != Integer.MIN_VALUE) {
            params.height = height;
        }
    }

    /** Add a Style's margin to layout params that may already carry spacing. */
    private void applyMargin(ViewGroup.MarginLayoutParams params, JSONObject style) {
        if (style == null) {
            return;
        }
        JSONArray margin = style.optJSONArray("margin");
        if (margin == null || margin.length() != 4) {
            return;
        }
        // Add rather than assign: a container's spacing and a Divider's inset
        // have already been written into these fields.
        params.leftMargin += dp(margin.optInt(0));
        params.topMargin += dp(margin.optInt(1));
        params.rightMargin += dp(margin.optInt(2));
        params.bottomMargin += dp(margin.optInt(3));
    }

    /**
     * Read a Style dimension.
     *
     * Accepts a number in dp or one of the names the framework documents:
     * "match"/"fill" for MATCH_PARENT and "wrap" for WRAP_CONTENT. Returns
     * Integer.MIN_VALUE when the key is absent, which no real size can be.
     */
    private int dimension(JSONObject style, String key) {
        if (!style.has(key)) {
            return Integer.MIN_VALUE;
        }
        Object raw = style.opt(key);
        if (raw instanceof Number) {
            return dp(((Number) raw).intValue());
        }
        String name = String.valueOf(raw).trim().toLowerCase(java.util.Locale.ROOT);
        if ("match".equals(name) || "fill".equals(name) || "match_parent".equals(name)) {
            return ViewGroup.LayoutParams.MATCH_PARENT;
        }
        if ("wrap".equals(name) || "wrap_content".equals(name)) {
            return ViewGroup.LayoutParams.WRAP_CONTENT;
        }
        return Integer.MIN_VALUE;
    }

    /** Position a single child across the container's axis. */
    private void applyCrossGravity(
            LinearLayout.LayoutParams params, int orientation, String crossAlign) {
        if (crossAlign.isEmpty() || "stretch".equals(crossAlign)) {
            return;
        }
        boolean vertical = orientation == LinearLayout.VERTICAL;
        if (vertical) {
            params.gravity = "center".equals(crossAlign)
                    ? Gravity.CENTER_HORIZONTAL
                    : ("end".equals(crossAlign) ? Gravity.END : Gravity.START);
        } else {
            params.gravity = "center".equals(crossAlign)
                    ? Gravity.CENTER_VERTICAL
                    : ("end".equals(crossAlign) ? Gravity.BOTTOM : Gravity.TOP);
        }
    }

    /** Combine main-axis and cross-axis alignment into a container gravity. */
    private int gravityFor(int orientation, String align, String crossAlign) {
        boolean vertical = orientation == LinearLayout.VERTICAL;
        int main = mainGravity(align, vertical);
        int cross;
        if (crossAlign.isEmpty()) {
            cross = vertical ? 0 : Gravity.CENTER_VERTICAL;
        } else if ("center".equals(crossAlign)) {
            cross = vertical ? Gravity.CENTER_HORIZONTAL : Gravity.CENTER_VERTICAL;
        } else if ("end".equals(crossAlign)) {
            cross = vertical ? Gravity.END : Gravity.BOTTOM;
        } else if ("start".equals(crossAlign)) {
            cross = vertical ? Gravity.START : Gravity.TOP;
        } else {
            cross = 0;  // stretch is expressed through the child's params
        }
        return main | cross;
    }

    /** Gravity along the container's own axis. */
    private int mainGravity(String align, boolean vertical) {
        if ("center".equals(align)) {
            return vertical ? Gravity.CENTER_VERTICAL : Gravity.CENTER_HORIZONTAL;
        }
        if ("end".equals(align)) {
            return vertical ? Gravity.BOTTOM : Gravity.END;
        }
        return vertical ? Gravity.TOP : Gravity.START;
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
        int orientation = horizontal ? LinearLayout.HORIZONTAL : LinearLayout.VERTICAL;
        content.setOrientation(orientation);
        int spacing = dp(props.optInt("spacing", 0));
        JSONArray children = node.optJSONArray("children");
        if (children != null) {
            for (int i = 0; i < children.length(); i++) {
                JSONObject childNode = children.getJSONObject(i);
                // Reuse the Row/Column sizing rules so a scrolled child gets
                // the same margins, flex shares and spacer sizes it would in
                // a plain Column.
                LinearLayout.LayoutParams params = childParams(childNode, orientation, "");
                if (spacing > 0 && i > 0) {
                    if (horizontal) {
                        params.leftMargin += spacing;
                    } else {
                        params.topMargin += spacing;
                    }
                }
                content.addView(buildChild(childNode), params);
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

    /**
     * A grid of equal-width columns.
     *
     * Implemented as a column of weighted rows rather than GridLayout: weights
     * guarantee identical column widths whatever the cell contents, which is
     * the property GridLayout only offers from API 21 with extra flags, and
     * every cell keeps working with the in-place update path.
     */
    private View buildGrid(JSONObject node, JSONObject props) throws JSONException {
        int columns = Math.max(1, props.optInt("columns", 2));
        int rowSpacing = dp(props.optInt("row_spacing", 0));
        int columnSpacing = dp(props.optInt("column_spacing", 0));

        LinearLayout grid = new LinearLayout(context);
        grid.setOrientation(LinearLayout.VERTICAL);

        JSONArray children = node.optJSONArray("children");
        int count = children == null ? 0 : children.length();
        for (int start = 0; start < count; start += columns) {
            LinearLayout row = new LinearLayout(context);
            row.setOrientation(LinearLayout.HORIZONTAL);
            for (int column = 0; column < columns; column++) {
                int index = start + column;
                LinearLayout.LayoutParams params =
                        new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
                if (column > 0) {
                    params.leftMargin = columnSpacing;
                }
                // Pad the final row with empty cells so the columns of a
                // partially filled row keep the width of the ones above.
                View cell;
                if (index < count) {
                    JSONObject childNode = children.getJSONObject(index);
                    cell = buildChild(childNode);
                    // A cell keeps its own margin; its width is owned by the
                    // grid, so only the margins are taken from the style.
                    applyMargin(params, childNode.optJSONObject("style"));
                } else {
                    cell = new View(context);
                }
                row.addView(cell, params);
            }
            LinearLayout.LayoutParams rowParams = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            if (start > 0) {
                rowParams.topMargin = rowSpacing;
            }
            grid.addView(row, rowParams);
        }
        return grid;
    }

    /**
     * Insets its content by the real window insets.
     *
     * The values are read from the view tree at attach time, so the content
     * clears the notch, status bar and gesture bar on any device instead of a
     * hard-coded guess. Below API 20 there are no insets to speak of, and the
     * optional `minimum` padding still applies.
     */
    private View buildSafeArea(JSONObject node, final JSONObject props) throws JSONException {
        final LinearLayout frame = new LinearLayout(context);
        frame.setOrientation(LinearLayout.VERTICAL);

        JSONArray children = node.optJSONArray("children");
        if (children != null) {
            for (int i = 0; i < children.length(); i++) {
                frame.addView(buildChild(children.getJSONObject(i)),
                        new LinearLayout.LayoutParams(
                                ViewGroup.LayoutParams.MATCH_PARENT,
                                ViewGroup.LayoutParams.WRAP_CONTENT));
            }
        }

        final int minimum = dp(props.optInt("minimum", 0));
        frame.setPadding(minimum, minimum, minimum, minimum);
        if (android.os.Build.VERSION.SDK_INT >= 20) {
            frame.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
                @Override
                public android.view.WindowInsets onApplyWindowInsets(
                        View view, android.view.WindowInsets insets) {
                    view.setPadding(
                            Math.max(minimum, props.optBoolean("left", true)
                                    ? insets.getSystemWindowInsetLeft() : 0),
                            Math.max(minimum, props.optBoolean("top", true)
                                    ? insets.getSystemWindowInsetTop() : 0),
                            Math.max(minimum, props.optBoolean("right", true)
                                    ? insets.getSystemWindowInsetRight() : 0),
                            Math.max(minimum, props.optBoolean("bottom", true)
                                    ? insets.getSystemWindowInsetBottom() : 0));
                    return insets;
                }
            });
            frame.requestApplyInsets();
        }
        return frame;
    }

    /**
     * Expanded / Flexible: a transparent wrapper.
     *
     * The interesting part — the weight — is applied by the parent in
     * {@link #childParams}; here we only need a container that passes its own
     * size straight through to the single child.
     */
    private View buildFlex(JSONObject node) throws JSONException {
        LinearLayout holder = new LinearLayout(context);
        holder.setOrientation(LinearLayout.VERTICAL);
        JSONArray children = node.optJSONArray("children");
        if (children != null && children.length() > 0) {
            holder.addView(buildChild(children.getJSONObject(0)),
                    new LinearLayout.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT,
                            ViewGroup.LayoutParams.MATCH_PARENT));
        }
        return holder;
    }

    private View buildDivider(JSONObject props) {
        // Like Spacer, this leaf never sets its own layout params: the parent
        // container owns them and a mismatched type throws at runtime.
        View line = new View(context);
        line.setBackgroundColor(parseColor(props.optString("color", "#1F000000"),
                Color.parseColor("#1F000000")));
        int thickness = dp(Math.max(1, props.optInt("thickness", 1)));
        if (props.optBoolean("vertical", false)) {
            line.setMinimumWidth(thickness);
        } else {
            line.setMinimumHeight(thickness);
        }
        return line;
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

    private View buildCheckbox(final String id, JSONObject props) {
        CheckBox checkbox = new CheckBox(context);
        checkbox.setChecked(props.optBoolean("checked", false));
        checkbox.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(CompoundButton view, boolean checked) {
                Native.dispatchEvent(id, "toggle", checked ? "true" : "false");
            }
        });
        return checkbox;
    }

    private View buildSlider(final String id, JSONObject props) {
        SeekBar seek = new SeekBar(context);
        double minimum = props.optDouble("minimum", 0);
        double maximum = props.optDouble("maximum", 100);
        int steps = Math.max(1, (int) Math.round(maximum - minimum));
        seek.setMax(steps);
        seek.setProgress((int) Math.round(props.optDouble("value", 0) - minimum));
        seek.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar bar, int progress, boolean fromUser) {
                if (fromUser) {
                    Native.dispatchEvent(id, "change",
                            String.valueOf(minimum + progress));
                }
            }

            @Override
            public void onStartTrackingTouch(SeekBar bar) {
            }

            @Override
            public void onStopTrackingTouch(SeekBar bar) {
            }
        });
        return seek;
    }

    private View buildRatingBar(final String id, JSONObject props) {
        RatingBar rating = new RatingBar(context);
        int maximum = Math.max(1, props.optInt("maximum", 5));
        rating.setNumStars(maximum);
        rating.setMax(maximum);
        rating.setStepSize(1f);
        rating.setRating((float) props.optDouble("rating", 0));
        rating.setOnRatingBarChangeListener(new RatingBar.OnRatingBarChangeListener() {
            @Override
            public void onRatingChanged(RatingBar bar, float value, boolean fromUser) {
                if (fromUser) {
                    Native.dispatchEvent(id, "change", String.valueOf(value));
                }
            }
        });
        return rating;
    }

    private View buildDropdown(final String id, JSONObject props) {
        Spinner spinner = new Spinner(context);
        JSONArray options = props.optJSONArray("options");
        String[] entries = new String[options == null ? 0 : options.length()];
        for (int i = 0; i < entries.length; i++) {
            entries[i] = options.optString(i, "");
        }
        android.widget.ArrayAdapter<String> adapter = new android.widget.ArrayAdapter<>(
                context, android.R.layout.simple_spinner_item, entries);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinner.setAdapter(adapter);
        String selected = props.optString("value", entries.length > 0 ? entries[0] : "");
        for (int i = 0; i < entries.length; i++) {
            if (entries[i].equals(selected)) {
                spinner.setSelection(i);
                break;
            }
        }
        spinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(
                    android.widget.AdapterView<?> parent, View view, int position, long itemId) {
                Native.dispatchEvent(id, "change",
                        String.valueOf(entries[position]));
            }

            @Override
            public void onNothingSelected(android.widget.AdapterView<?> parent) {
            }
        });
        return spinner;
    }

    private View buildChip(final String id, JSONObject props) {
        Button chip = new Button(context);
        chip.setText(props.optString("text", ""));
        chip.setAllCaps(false);
        if (props.optBoolean("selected", false)) {
            chip.setTextColor(Color.parseColor("#FFFFFF"));
            chip.setBackgroundColor(parseColor(props.optString("selectedColor", "#3F51B5"),
                    Color.parseColor("#3F51B5")));
        }
        chip.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Native.dispatchEvent(id, "press", "");
            }
        });
        return chip;
    }

    private View buildBadge(JSONObject props) {
        TextView badge = new TextView(context);
        badge.setText(props.optString("text", ""));
        badge.setTextColor(parseColor(props.optString("color", "#FFFFFF"),
                Color.parseColor("#FFFFFF")));
        badge.setBackgroundColor(parseColor(props.optString("background", "#3F51B5"),
                Color.parseColor("#3F51B5")));
        badge.setGravity(Gravity.CENTER);
        int pad = dp(6);
        badge.setPadding(pad, dp(2), pad, dp(2));
        return badge;
    }

    private View buildStepper(final String id, JSONObject props) {
        LinearLayout row = new LinearLayout(context);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER);

        Button minus = new Button(context);
        minus.setText("−");
        minus.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Native.dispatchEvent(id, "decrement", "");
            }
        });
        TextView value = new TextView(context);
        value.setText(String.valueOf(props.optInt("value", 0)));
        value.setGravity(Gravity.CENTER);
        value.setPadding(dp(12), 0, dp(12), 0);
        value.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
        Button plus = new Button(context);
        plus.setText("+");
        plus.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Native.dispatchEvent(id, "increment", "");
            }
        });

        row.addView(minus);
        row.addView(value);
        row.addView(plus);
        row.setTag(id);  // the outer row carries the widget id
        return row;
    }

    private View buildRadioButton(final String id, JSONObject props) {
        RadioButton radio = new RadioButton(context);
        radio.setText(props.optString("text", ""));
        radio.setChecked(props.optBoolean("selected", false));
        radio.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Native.dispatchEvent(id, "press", "");
            }
        });
        return radio;
    }

    private View buildRadioGroup(JSONObject node, final String id, JSONObject props)
            throws JSONException {
        RadioGroup group = new RadioGroup(context);
        group.setOrientation(LinearLayout.VERTICAL);
        JSONArray children = node.optJSONArray("children");
        if (children != null) {
            for (int i = 0; i < children.length(); i++) {
                JSONObject childNode = children.getJSONObject(i);
                View child = buildChild(childNode);
                group.addView(child);
                if (childNode.optJSONObject("props") != null
                        && childNode.optJSONObject("props").optBoolean("selected", false)) {
                    group.check(child.getId() == 0 ? -1 : child.getId());
                }
            }
        }
        // The outer group carries the widget id.
        group.setTag(id);
        return group;
    }

    private View buildSegmented(final String id, JSONObject props) {
        LinearLayout row = new LinearLayout(context);
        row.setOrientation(LinearLayout.HORIZONTAL);
        JSONArray options = props.optJSONArray("options");
        String selected = props.optString("value", "");
        if (options != null) {
            for (int i = 0; i < options.length(); i++) {
                final String label = options.optString(i, "");
                Button segment = new Button(context);
                segment.setText(label);
                segment.setAllCaps(false);
                if (label.equals(selected)) {
                    segment.setTextColor(Color.parseColor("#FFFFFF"));
                    segment.setBackgroundColor(Color.parseColor("#3F51B5"));
                }
                segment.setOnClickListener(new View.OnClickListener() {
                    @Override
                    public void onClick(View v) {
                        Native.dispatchEvent(id, "change", label);
                    }
                });
                row.addView(segment);
            }
        }
        row.setTag(id);
        return row;
    }

    private View buildLink(final String id, JSONObject props) {
        TextView link = new TextView(context);
        link.setText(props.optString("text", ""));
        link.setTextColor(Color.parseColor("#3F51B5"));
        link.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        final String url = props.optString("url", "");
        link.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                // Open the URL in the system browser directly from Java (no JNI
                // round-trip), so links work even with an older libpymobile.so.
                if (url != null && !url.isEmpty()) {
                    DeviceServices.openUrl(context, url);
                } else {
                    Native.dispatchEvent(id, "press", "");
                }
            }
        });
        return link;
    }

    private View buildProgressText(final String id, JSONObject props) {
        ProgressBar bar = new ProgressBar(context, null,
                android.R.attr.progressBarStyleHorizontal);
        bar.setMax(Math.max(1, (int) props.optDouble("maximum", 100)));
        bar.setProgress((int) props.optDouble("value", 0));
        // The label is separate; we keep the bar itself simple and let the
        // Python side present the "Downloading 42%" text via a sibling label.
        bar.setTag(id);
        return bar;
    }

    private View buildDataTable(JSONObject node, JSONObject props) throws JSONException {
        LinearLayout table = new LinearLayout(context);
        table.setOrientation(LinearLayout.VERTICAL);
        JSONArray headers = props.optJSONArray("headers");
        JSONArray rows = props.optJSONArray("rows");
        if (headers != null) {
            LinearLayout head = new LinearLayout(context);
            head.setOrientation(LinearLayout.HORIZONTAL);
            for (int i = 0; i < headers.length(); i++) {
                TextView cell = new TextView(context);
                cell.setText(headers.optString(i, ""));
                cell.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
                cell.setPadding(dp(8), dp(4), dp(8), dp(4));
                head.addView(cell);
            }
            table.addView(head);
        }
        if (rows != null) {
            for (int r = 0; r < rows.length(); r++) {
                LinearLayout row = new LinearLayout(context);
                row.setOrientation(LinearLayout.HORIZONTAL);
                JSONArray cells = rows.optJSONArray(r);
                for (int c = 0; c < (cells == null ? 0 : cells.length()); c++) {
                    TextView cell = new TextView(context);
                    cell.setText(cells.optString(c, ""));
                    cell.setPadding(dp(8), dp(4), dp(8), dp(4));
                    row.addView(cell);
                }
                table.addView(row);
            }
        }
        return table;
    }

    private View buildAvatar(JSONObject props) {
        TextView avatar = new TextView(context);
        String text = props.optString("text", "");
        if (text.length() > 2) {
            text = text.substring(0, 2);
        }
        avatar.setText(text.toUpperCase());
        avatar.setTextColor(parseColor(props.optString("color", "#FFFFFF"),
                Color.parseColor("#FFFFFF")));
        avatar.setGravity(Gravity.CENTER);
        int size = dp(props.optInt("size", 48));
        avatar.setBackgroundColor(parseColor(props.optString("background", "#3F51B5"),
                Color.parseColor("#3F51B5")));
        avatar.setMinimumWidth(size);
        avatar.setMinimumHeight(size);
        return avatar;
    }

    /**
     * List is already virtualised on the Python side (only a window of rows is
     * serialised), so here it is a plain vertical stack of its children.
     */
    private View buildList(JSONObject node, JSONObject props) throws JSONException {
        LinearLayout list = new LinearLayout(context);
        list.setOrientation(LinearLayout.VERTICAL);
        int spacing = dp(props.optInt("spacing", 0));
        JSONArray children = node.optJSONArray("children");
        if (children != null) {
            for (int i = 0; i < children.length(); i++) {
                LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT);
                if (spacing > 0 && i > 0) {
                    params.topMargin = spacing;
                }
                list.addView(buildChild(children.getJSONObject(i)), params);
            }
        }
        return list;
    }

    /** A tappable list row: title + subtitle + trailing, dispatching "press". */
    private View buildListTile(final String id, JSONObject props) {
        LinearLayout row = new LinearLayout(context);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(12), dp(10), dp(12), dp(10));
        // A subtle ripple requires a background; use a selectable borderless item.
        if (android.os.Build.VERSION.SDK_INT >= 21) {
            android.content.res.TypedArray a = context.obtainStyledAttributes(
                    new int[]{android.R.attr.selectableItemBackground});
            row.setBackgroundResource(a.getResourceId(0, 0));
            a.recycle();
        }

        LinearLayout texts = new LinearLayout(context);
        texts.setOrientation(LinearLayout.VERTICAL);
        TextView title = new TextView(context);
        title.setText(props.optString("title", ""));
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        title.setTextColor(Color.parseColor("#212121"));
        texts.addView(title);
        String subtitle = props.optString("subtitle", "");
        if (!subtitle.isEmpty()) {
            TextView sub = new TextView(context);
            sub.setText(subtitle);
            sub.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
            sub.setTextColor(Color.parseColor("#757575"));
            texts.addView(sub);
        }

        LinearLayout.LayoutParams textsParams = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        row.addView(texts, textsParams);

        String trailing = props.optString("trailing", "");
        if (!trailing.isEmpty()) {
            TextView trailingView = new TextView(context);
            trailingView.setText(trailing);
            trailingView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
            trailingView.setTextColor(Color.parseColor("#757575"));
            row.addView(trailingView);
        }

        row.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Native.dispatchEvent(id, "press", "");
            }
        });
        if (props.optBoolean("long_pressable", false)) {
            row.setOnLongClickListener(new View.OnLongClickListener() {
                @Override
                public boolean onLongClick(View v) {
                    v.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS);
                    Native.dispatchEvent(id, "long_press", "");
                    return true;
                }
            });
        }
        return row;
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

        // Re-apply style (background, padding, elevation, ...) so theme switches
        // and styling changes are reflected without a full rebuild.
        applyStyle(view, node.optJSONObject("style"));

        // ListTile is a row built from props (no serialised children), so update
        // its title text in place rather than treating it as a child container.
        if ("ListTile".equals(type) && view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                View child = group.getChildAt(i);
                if (child instanceof LinearLayout) {
                    ViewGroup texts = (ViewGroup) child;
                    if (texts.getChildCount() > 0 && texts.getChildAt(0) instanceof TextView) {
                        ((TextView) texts.getChildAt(0))
                                .setText(props.optString("title", ""));
                    }
                }
            }
            return true;
        }

        // Components that build a composite view from props but serialise as a
        // leaf (no "children" in the tree). The generic ViewGroup walk below
        // would compare the live child count against zero and return false,
        // forcing a full rebuild of the ENTIRE screen on every render — which
        // closes the keyboard, resets scroll and loses widget state. So update
        // them in place as leaves instead.
        if ("Stepper".equals(type) && view instanceof ViewGroup) {
            // Layout: [minus button][value text][plus button]
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                View child = group.getChildAt(i);
                if (child instanceof TextView) {
                    ((TextView) child).setText(String.valueOf(props.optInt("value", 0)));
                }
            }
            return true;
        }
        if ("SegmentedButtons".equals(type) && view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            String selected = props.optString("value", "");
            for (int i = 0; i < group.getChildCount(); i++) {
                View child = group.getChildAt(i);
                if (child instanceof TextView) {
                    boolean isSelected = ((TextView) child).getText().toString()
                            .equals(selected);
                    if (isSelected) {
                        child.setBackgroundColor(Color.parseColor("#3F51B5"));
                        ((TextView) child).setTextColor(Color.parseColor("#FFFFFF"));
                    } else {
                        child.setBackgroundColor(Color.TRANSPARENT);
                        ((TextView) child).setTextColor(Color.parseColor("#212121"));
                    }
                }
            }
            return true;
        }
        if ("DataTable".equals(type)) {
            // DataTable content is rebuilt by the Python side when it changes;
            // accept the update so the screen is not rebuilt wholesale.
            return true;
        }

        if (view instanceof ViewGroup) {
            JSONArray children = node.optJSONArray("children");
            ViewGroup group = (ViewGroup) view;

            // A Grid nests its cells in one LinearLayout per row, so the flat
            // list of children in the tree has to be walked row by row.
            if ("Grid".equals(type)) {
                return updateGrid(group, props, children);
            }

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

        if (view instanceof CheckBox) {
            // CheckBox extends CompoundButton extends Button, so this must come
            // before the Button branch. CompoundButton has no public getter for
            // its listener, so we cannot save/restore it; setChecked here is a
            // programmatic sync and the Python side guards against echo loops.
            CheckBox checkbox = (CheckBox) view;
            boolean checked = props.optBoolean("checked", false);
            if (checkbox.isChecked() != checked) {
                checkbox.setChecked(checked);
            }
            return true;
        }
        if (view instanceof SeekBar) {
            SeekBar seek = (SeekBar) view;
            double minimum = props.optDouble("minimum", 0);
            int progress = (int) Math.round(props.optDouble("value", 0) - minimum);
            if (seek.getProgress() != progress) {
                seek.setProgress(progress);
            }
            return true;
        }
        if (view instanceof RatingBar) {
            RatingBar rating = (RatingBar) view;
            float value = (float) props.optDouble("rating", 0);
            if (Math.abs(rating.getRating() - value) > 1e-3f) {
                rating.setOnRatingBarChangeListener(null);
                rating.setRating(value);
                // Re-attach is intentionally skipped: the build path owns the
                // listener and a partial tree rebuild re-creates the view.
            }
            return true;
        }
        if (view instanceof Spinner) {
            // Selection is user-driven; do not overwrite it from Python.
            return true;
        }
        if (view instanceof Button) {
            ((Button) view).setText(props.optString("text", ""));
            return true;
        }
        if (view instanceof View && "Divider".equals(type)) {
            view.setBackgroundColor(parseColor(props.optString("color", "#1F000000"),
                    Color.parseColor("#1F000000")));
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

    /** Patch a grid in place, mapping the flat child list onto its rows. */
    private boolean updateGrid(ViewGroup grid, JSONObject props, JSONArray children)
            throws JSONException {
        int columns = Math.max(1, props.optInt("columns", 2));
        int count = children == null ? 0 : children.length();
        int expectedRows = (count + columns - 1) / columns;
        if (grid.getChildCount() != expectedRows) {
            return false;
        }
        for (int rowIndex = 0; rowIndex < expectedRows; rowIndex++) {
            View row = grid.getChildAt(rowIndex);
            if (!(row instanceof ViewGroup)) {
                return false;
            }
            ViewGroup cells = (ViewGroup) row;
            if (cells.getChildCount() != columns) {
                return false;
            }
            for (int column = 0; column < columns; column++) {
                int index = rowIndex * columns + column;
                if (index >= count) {
                    break;  // the padding cells of the last row carry no state
                }
                if (!updateNode(cells.getChildAt(column), children.getJSONObject(index))) {
                    return false;
                }
            }
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

        // margin, width and height are applied in applyBoxStyle() instead:
        // this method runs before the view has a parent, so its layout params
        // do not exist yet and anything written here would be discarded.

        if (style.has("elevation") && android.os.Build.VERSION.SDK_INT >= 21) {
            float elevation = dp(style.optInt("elevation"));
            view.setElevation(elevation);
            // A shadow needs something opaque to fall from; a view with no
            // background casts none, which looks like elevation being ignored.
            if (!style.has("background")) {
                view.setBackgroundColor(Color.WHITE);
            }
        }

        applyConstraints(view, style);
    }

    /**
     * Size constraints: min/max width and height, plus aspect ratio.
     *
     * Android has no single API for this, so each piece uses the mechanism
     * that actually works on a plain View: minimums are view properties,
     * maximums and the ratio are enforced by a layout listener that clamps the
     * measured size once the parent has laid the view out.
     */
    private void applyConstraints(final View view, final JSONObject style) {
        boolean hasMin = style.has("min_width") || style.has("min_height");
        boolean hasMax = style.has("max_width") || style.has("max_height");
        boolean hasRatio = style.has("aspect_ratio");
        if (!hasMin && !hasMax && !hasRatio) {
            return;
        }

        if (style.has("min_width")) {
            view.setMinimumWidth(dp(style.optInt("min_width")));
        }
        if (style.has("min_height")) {
            view.setMinimumHeight(dp(style.optInt("min_height")));
        }
        if (!hasMax && !hasRatio) {
            return;
        }

        final int maxWidth = style.has("max_width") ? dp(style.optInt("max_width")) : 0;
        final int maxHeight = style.has("max_height") ? dp(style.optInt("max_height")) : 0;
        final double ratio = style.optDouble("aspect_ratio", 0);

        view.addOnLayoutChangeListener(new View.OnLayoutChangeListener() {
            @Override
            public void onLayoutChange(View v, int left, int top, int right, int bottom,
                    int oldLeft, int oldTop, int oldRight, int oldBottom) {
                ViewGroup.LayoutParams params = v.getLayoutParams();
                if (params == null) {
                    return;
                }
                int width = right - left;
                int height = bottom - top;
                int wantWidth = width;
                int wantHeight = height;

                if (maxWidth > 0 && wantWidth > maxWidth) {
                    wantWidth = maxWidth;
                }
                if (maxHeight > 0 && wantHeight > maxHeight) {
                    wantHeight = maxHeight;
                }
                if (ratio > 0 && wantWidth > 0) {
                    wantHeight = (int) Math.round(wantWidth / ratio);
                }
                if (wantWidth == width && wantHeight == height) {
                    return;
                }
                params.width = wantWidth;
                params.height = wantHeight;
                // requestLayout from inside a layout pass is dropped; post it.
                v.post(new Runnable() {
                    @Override
                    public void run() {
                        v.requestLayout();
                    }
                });
            }
        });
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
