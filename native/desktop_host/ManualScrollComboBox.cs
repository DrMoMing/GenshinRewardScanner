// Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// AI-generated project code: written and modified with OpenAI Codex.
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Controls.Primitives;
using System.Windows.Media;

namespace NativeWpf
{
    // The issue menu scrolls only through explicit wheel, scrollbar or key input.
    public sealed class ManualScrollComboBox : ComboBox
    {
        protected override DependencyObject GetContainerForItemOverride()
        {
            return new ManualScrollComboBoxItem();
        }

        protected override void OnPreviewMouseMove(MouseEventArgs e)
        {
            // Keep ComboBox's captured-pointer edge navigation inactive.
            // A scrollbar thumb still needs its normal MouseMove/DragDelta path.
            if (IsDropDownOpen && !IsScrollBarInput(e.OriginalSource as DependencyObject)
                && !IsScrollBarInput(Mouse.Captured as DependencyObject)) e.Handled = true;
            base.OnPreviewMouseMove(e);
        }

        static bool IsScrollBarInput(DependencyObject value)
        {
            while (value != null) {
                if (value is ScrollBar) return true;
                value = value is Visual ? VisualTreeHelper.GetParent(value) : LogicalTreeHelper.GetParent(value);
            }
            return false;
        }
    }

    public sealed class ManualScrollComboBoxItem : ComboBoxItem
    {
        protected override void OnMouseEnter(MouseEventArgs e)
        {
            // Pointer hover must not focus/bring a partially visible row into view.
            // Click selection and keyboard focus retain ComboBoxItem's defaults.
        }
    }
}
