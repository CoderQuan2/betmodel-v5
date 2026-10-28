## 2024-05-24 - Add ARIA Labels to Icon Buttons
**Learning:** Icon-only buttons often lack accessibility context for screen readers. In Flet, the `tooltip` property often serves as an accessible label.
**Action:** Adding `tooltip` strings to `ft.IconButton` instances that lack them improves accessibility for these elements.
