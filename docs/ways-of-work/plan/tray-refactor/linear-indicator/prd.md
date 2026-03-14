# PRD — Linear Tray Indicator (High Density)

> **Feature Name:** Linear Tray Indicator
> **Epic:** UI/UX Tray Experience Refactor
> **Status:** Draft

## 1. Goal

- **Problem:** The current circular arc icon in the system tray (22x22px) is too small and lacks visual clarity. The thin 3px stroke makes it difficult for users to distinguish between usage levels (e.g., 70% vs 90%) at a quick glance, and it only represents one dimension of usage effectively.
- **Solution:** Replace the circular arc with a high-density linear indicator. It will use the full horizontal width (22px) to display two distinct bars: a thick primary bar for the 5-hour usage window and a secondary thin line (mercury line) for the 7-day window.
- **Impact:** Improved legibility of API usage directly from the tray, reduced cognitive load for the user, and a more modern, integrated aesthetic for GNOME/GTK environments.

## 2. User Personas

- **The Intensive User:** Needs to know exactly how much budget is left before hitting a 429 rate limit during a coding session.
- **The Long-term Planner:** Monitors 7-day trends to avoid running out of monthly/weekly tokens unexpectedly.

## 3. User Stories

- **As an intensive user**, I want to see a thick, color-coded bar in the tray so that I can instantly see my 5-hour usage level without opening the popup.
- **As a long-term planner**, I want a secondary indicator for my 7-day usage so that I can monitor my weekly trend alongside my immediate consumption.
- **As a user**, I want the icon to change color (green/amber/red) based on the most critical (highest) usage tier so that I am alerted to potential limits.

## 4. Requirements

### Functional Requirements
- **FR1: Linear Transformation:** The icon generator (`icons.py`) must be updated to render horizontal bars instead of circular arcs.
- **FR2: Dual Indicators:** The icon must render two distinct bars:
    - **Primary Bar:** Occupies the middle 60% of the vertical space (approx. 6-8px height).
    - **Secondary Bar:** A thin line (1-2px) positioned either above or below the primary bar.
- **FR3: Color Mapping:** Both bars must use the established color scheme (Green: <70%, Amber: 70-90%, Red: >=90%) based on their respective utilization levels.
- **FR4: Dynamic Generation:** The script must continue to generate static PNGs for the GTK tray (as per current architecture) but with the new linear design.
- **FR5: Asset Mapping:** Update `indicator/theme.py` and `indicator/icons.py` to ensure the correct percentages (45%, 80%, 95%) are used for the generated static assets.

### Non-Functional Requirements
- **NFR1: Visibility:** The bar must have a 10% opacity "track" background to show the full 100% capacity range.
- **NFR2: Performance:** Icon generation must remain fast and synchronous at startup.
- **NFR3: Aesthetic:** Use rounded caps (pills) for the primary bar to match modern GNOME shell elements.

## 5. Acceptance Criteria

| Requirement | Acceptance Criteria |
| :--- | :--- |
| **Linear Bar** | Given the application starts, the tray icon must be a horizontal bar filling 22px width. |
| **Dual Data** | Given a 5-hour usage of 80% and a 7-day usage of 40%, the thick bar must be amber and 80% long, while the thin line must be green and 40% long. |
| **Alerting** | Given usage >90%, the primary bar must be red (#C01C28). |
| **Background Track** | Given any usage level, a faint background must be visible representing the full 100% length. |

## 6. Out of Scope

- Animation of the bars within the tray (limited by GTK `StatusIcon` and static PNGs).
- Text/percentages inside the tray icon (not readable at 22px).
- Ability to toggle between circular and linear modes (permanent migration).

## 7. Next Steps

1.  Update `indicator/icons.py` to implement `_render_linear_icon`.
2.  Adjust `indicator/theme.py` if new color constants or spacing are needed.
3.  Regenerate assets and verify in a GNOME tray.
