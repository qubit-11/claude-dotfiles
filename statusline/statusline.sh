#!/usr/bin/env bash
# Claude Code status line, two lines:
#   📁 folder │ 🌿 branch                              (own line: full width)
#   ctx 42% │ Opus 5.5 high │ 5h 23% ↻4h50 │ 7d 85% ↻5d9h │ Example Org
# ↻ = time left until the limit resets (dimmed; hidden when unknown or past).
# All values come from the JSON Claude Code sends on stdin, so every
# profile (claude1, claude2, ...) shows its own account's limits.
# Colours: green = fine, orange = warning, red = act now.
# Claude Code sends ctx and limits only after the session's first response.
# Until then ctx shows a dimmed "-" and limits their last known value, "~23%".

# --- Thresholds -------------------------------------------------------------
# Context: coloured by token count (quality loss depends on tokens, not on
# window size), or by window fill when the window is small (200k: the token
# limits are never or barely reached, auto-compact comes first). Whichever
# limit is hit first wins.
# Evidence: Opus 4.6 long-context retrieval ~93% at 256k, ~76% at 1M tokens.
CTX_ORANGE_TOKENS=250000
CTX_RED_TOKENS=500000
CTX_ORANGE_WINDOW_PCT=80
CTX_RED_WINDOW_PCT=90
# Limits: orange = only one more big task fits, red = less than one fits.
# One big task (median implementation, measured from session history
# 2026-11-25): ~30% of the 5h window, ~6% of the 7d window.
#   orange from 100 - 2*task, red from 100 - task
LIMIT_5H_ORANGE=40;  LIMIT_5H_RED=70
LIMIT_7D_ORANGE=88;  LIMIT_7D_RED=94

# Ticket keys in the folder and branch name become clickable links to the
# tracker. Any case matches (folders use abc-123, branches ABC-123); links use
# upper case. The values belong to one environment, so they live in a local,
# untracked file beside the settings, e.g.:
#   JIRA_BROWSE_URL="https://example.atlassian.net/browse"
#   JIRA_KEY_REGEX='([Aa][Bb][Cc]-[0-9]+)'   # one capture group: the key
# Without it the names stay plain text.
JIRA_BROWSE_URL="" JIRA_KEY_REGEX=""
STATUSLINE_LOCAL_ENV="$HOME/.claude/statusline.local.env"
# shellcheck source=/dev/null
[[ -r $STATUSLINE_LOCAL_ENV ]] && source "$STATUSLINE_LOCAL_ENV"

# Columns Claude Code takes from the terminal width for the status bar:
# 2 indent left + 2 right (measured: 78-column terminal showed 74 columns).
STATUS_MARGIN=4
# ----------------------------------------------------------------------------

input=$(cat)
export LC_ALL=en_US.UTF-8   # count characters, not bytes, when measuring names

# Tab-separated; empty values become "-" so read keeps the field positions.
# Reset times become epoch seconds (number, ms number or ISO string accepted).
IFS=$'\t' read -r model effort dir ctx_pct ctx_tokens five five_reset week week_reset < <(jq -r '
def epoch: if type == "number" then (if . > 1e12 then . / 1000 else . end | floor)
  elif type == "string" then (try (sub("\\.[0-9]+"; "") | fromdateiso8601) catch null)
  else null end;
[
  (.model.display_name // "?"),
  (.effort.level // ""),
  (.workspace.current_dir // .cwd // ""),
  (.context_window.used_percentage // ""),
  (.context_window.current_usage
     | if . then (.input_tokens // 0) + (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0)
       else "" end),
  (.rate_limits.five_hour.used_percentage // ""),
  (.rate_limits.five_hour.resets_at | epoch),
  (.rate_limits.seven_day.used_percentage // ""),
  (.rate_limits.seven_day.resets_at | epoch)
] | map(if . == "" or . == null then "-" else tostring end) | @tsv' <<<"$input")

# Account: organisation this profile is logged in to. Profile 1 keeps its
# state in ~/.claude.json, other profiles in $CLAUDE_CONFIG_DIR/.claude.json.
if [[ -n $CLAUDE_CONFIG_DIR ]]; then state="$CLAUDE_CONFIG_DIR/.claude.json"; else state="$HOME/.claude.json"; fi
account=$(jq -r '.oauthAccount.organizationName // empty' "$state" 2>/dev/null)
account=${account:-?}

[[ $effort != "-" ]] && model+=" ${effort}"

dim=$'\e[2m' reset=$'\e[0m'
green=$'\e[32m' orange=$'\e[38;5;208m' red=$'\e[31m'
sep=" ${dim}│${reset} "

round() { printf '%.0f' "$1"; }

# colour_for VALUE ORANGE_FROM RED_FROM
colour_for() {
  if   (( $1 >= $3 )); then printf '%s' "$red"
  elif (( $1 >= $2 )); then printf '%s' "$orange"
  else                      printf '%s' "$green"; fi
}

# show LABEL VALUE COLOUR [MARK]: "label 42%" in colour ("~42%" with MARK ~),
# or dimmed "label -" when there is no value
show() {
  local label=$1 value=$2 colour=$3 mark=$4
  if [[ $value == "-" ]]; then printf '%s' "${dim}${label} -${reset}"
  else printf '%s' "${label} ${colour}${mark}${value}%${reset}"; fi
}

# until_reset RESET: dimmed " ↻5d9h" / " ↻4h50" / " ↻12m" (minutes rounded
# up), or nothing when the reset time is unknown or already past
until_reset() {
  [[ $1 == "-" ]] && return
  local left=$(( $1 - now )) d h m
  (( left <= 0 )) && return
  left=$(( (left + 59) / 60 * 60 ))
  d=$(( left / 86400 )) h=$(( left % 86400 / 3600 )) m=$(( left % 3600 / 60 ))
  if   (( d > 0 )); then printf ' %s↻%dd%dh%s' "$dim" "$d" "$h" "$reset"
  elif (( h > 0 )); then printf ' %s↻%dh%02d%s' "$dim" "$h" "$m" "$reset"
  else                   printf ' %s↻%dm%s' "$dim" "$m" "$reset"; fi
}

# --- Limits cache -------------------------------------------------------------
# One file per profile holds the last 5h/7d values and reset times. Before the
# first response of a session the cached values are shown with "~". A cached
# value can only be too low (usage on claude.ai, other machines or sessions is
# not seen); once its window has reset it shows 0.
limits_cache="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/statusline-limits.tsv"
c_five=- c_five_reset=- c_week=- c_week_reset=- c_line=""
tab=$'\t' num='([0-9]+|-)'
[[ -r $limits_cache ]] && c_line=$(<"$limits_cache")
if [[ $c_line =~ ^$num$tab$num$tab$num$tab$num$ ]]; then
  IFS=$'\t' read -r c_five c_five_reset c_week c_week_reset <<<"$c_line"
fi

now=$(date +%s)
# cached_value VALUE RESET: VALUE, or 0 when its window has reset since
cached_value() {
  if [[ $1 != "-" && $2 != "-" ]] && (( now >= $2 )); then printf 0
  else printf '%s' "$1"; fi
}

[[ $five != "-" ]] && five=$(round "$five")
[[ $week != "-" ]] && week=$(round "$week")
fresh=0; [[ $five != "-" || $week != "-" ]] && fresh=1
five_mark="" week_mark=""
[[ $five == "-" && $c_five != "-" ]] && five=$(cached_value "$c_five" "$c_five_reset") five_reset=$c_five_reset five_mark="~"
[[ $week == "-" && $c_week != "-" ]] && week=$(cached_value "$c_week" "$c_week_reset") week_reset=$c_week_reset week_mark="~"

# Write only when a value changed; temp file + mv, so parallel sessions never
# leave a half-written file.
if (( fresh )); then
  line="${five}${tab}${five_reset}${tab}${week}${tab}${week_reset}"
  if [[ $line != "$c_line" ]]; then
    tmp="${limits_cache}.$$"
    printf '%s\n' "$line" >"$tmp" 2>/dev/null && mv -f "$tmp" "$limits_cache"
  fi
fi
# ----------------------------------------------------------------------------

# Context colour: by tokens or by window fill, whichever is reached first
ctx_colour=$green
if [[ $ctx_pct != "-" ]]; then
  ctx_pct=$(round "$ctx_pct")
  tokens=0; [[ $ctx_tokens != "-" ]] && tokens=$ctx_tokens
  if   (( tokens >= CTX_RED_TOKENS || ctx_pct >= CTX_RED_WINDOW_PCT )); then ctx_colour=$red
  elif (( tokens >= CTX_ORANGE_TOKENS || ctx_pct >= CTX_ORANGE_WINDOW_PCT )); then ctx_colour=$orange
  fi
fi

five_colour=""; [[ $five != "-" ]] && five_colour=$(colour_for "$five" $LIMIT_5H_ORANGE $LIMIT_5H_RED)
week_colour=""; [[ $week != "-" ]] && week_colour=$(colour_for "$week" $LIMIT_7D_ORANGE $LIMIT_7D_RED)

# wrap_name ICON NAME MAX: print "ICON NAME", split over several lines if it is
# wider than MAX columns. Splits after - / _ where possible, continuation lines
# are indented to line up with the text after the icon. Icon + space = 3 columns.
wrap_name() {
  local icon=$1 rest=$2 max=$3 prefix="$1 " avail=$(( $3 - 3 )) chunk cut i
  (( avail < 10 )) && avail=10
  while (( ${#rest} > avail )); do
    chunk=${rest:0:avail} cut=0
    for (( i = avail - 1; i >= avail / 2; i-- )); do
      # never split inside a ticket key like ABC-123
      [[ ${chunk:i:1} == - && ${chunk:i-1:1} == [A-Za-z] && ${rest:i+1:1} == [0-9] ]] && continue
      [[ ${chunk:i:1} == [-/_] ]] && { cut=$(( i + 1 )); break; }
    done
    (( cut == 0 )) && cut=$avail
    printf '%s\n' "${prefix}${rest:0:cut}"
    # indent with braille blanks (U+2800): look like spaces, but Claude Code
    # strips real leading spaces from status lines
    rest=${rest:cut} prefix=$'⠀⠀⠀'
  done
  printf '%s' "${prefix}${rest}"
}

# Terminal hyperlinks (OSC 8). Added after measuring/splitting, since the
# escape codes take no visible space. An explicit link also stops terminals
# from guessing one (iTerm2 turned "AbCd/ABC-..." into http://abcd/...).
osc_link() {  # osc_link URL TEXT  (plain TEXT when URL or TEXT is empty)
  if [[ -n $1 && -n $2 ]]; then printf '\e]8;;%s\e\\%s\e]8;;\e\\' "$1" "$2"; else printf '%s' "$2"; fi
}

# link_name TEXT URL: ticket keys -> tracker, everything else -> URL (the branch
# or commit page; empty URL = plain text, used for the folder). TEXT may be
# several lines; icon and indent stay unlinked.
link_name() {
  local text=$1 url=$2 out="" line prefix body key n=0
  while IFS= read -r line || [[ -n $line ]]; do
    (( n++ )) && out+=$'\n'
    prefix=""
    [[ $line == "🌿 "* ]] && prefix="🌿 "
    [[ $line == "📁 "* ]] && prefix="📁 "
    [[ $line == $'⠀⠀⠀'* ]] && prefix=$'⠀⠀⠀'
    body=${line#"$prefix"}; out+=$prefix
    while [[ -n $JIRA_KEY_REGEX && -n $JIRA_BROWSE_URL && $body =~ $JIRA_KEY_REGEX ]]; do
      key=${BASH_REMATCH[1]}
      out+=$(osc_link "$url" "${body%%"$key"*}")$(osc_link "${JIRA_BROWSE_URL}/$(printf '%s' "$key" | tr '[:lower:]' '[:upper:]')" "$key")
      body=${body#*"$key"}
    done
    out+=$(osc_link "$url" "$body")
  done <<<"$text"
  printf '%s' "$out"
}

# web_url DIR: https address of the repository's origin remote (GitLab/GitHub)
web_url() {
  local u; u=$(command git -C "$1" remote get-url origin 2>/dev/null) || return
  u=${u%.git}
  case $u in
    git@*:*)        u=${u#git@}; u="https://${u%%:*}/${u#*:}" ;;
    ssh://*)        u=${u#ssh://}; u=${u#*@}; local host=${u%%/*}; u="https://${host%%:*}/${u#*/}" ;;
    http://*|https://*) u=${u/\/\/*@/\/\/} ;;
    *) return ;;
  esac
  printf '%s' "$u"
}

# Line 1: folder and branch, full names, never cut off. Claude Code passes the
# terminal width as COLUMNS. Both fit -> one line; otherwise each on its own
# line(s), split if a single name is wider than the terminal.
line1=""
if [[ $dir != "-" ]]; then
  folder=${dir##*/}
  # Branch; detached HEAD shows the commit; not a git repo shows nothing
  branch=$(command git -C "$dir" branch --show-current 2>/dev/null)
  branch_url=""
  if [[ -n $branch ]]; then
    repo_url=$(web_url "$dir")
    if [[ $repo_url == *github.com* ]]; then branch_url="${repo_url:+$repo_url/tree/$branch}"
    else branch_url="${repo_url:+$repo_url/-/tree/$branch}"; fi
  elif commit=$(command git -C "$dir" rev-parse --short HEAD 2>/dev/null); then
    branch="detached ${commit}"
    repo_url=$(web_url "$dir")
    if [[ $repo_url == *github.com* ]]; then branch_url="${repo_url:+$repo_url/commit/$commit}"
    else branch_url="${repo_url:+$repo_url/-/commit/$commit}"; fi
  fi
  max=$(( ${COLUMNS:-0} - STATUS_MARGIN ))
  one_line=$(( 3 + ${#folder} + 3 + 3 + ${#branch} ))   # icon+space, " │ ", icon+space
  [[ -z $branch ]] && one_line=$(( 3 + ${#folder} ))
  if (( max <= 0 || one_line <= max )); then
    line1=$(link_name "📁 ${folder}" "")
    [[ -n $branch ]] && line1+="${sep}$(link_name "🌿 ${branch}" "$branch_url")"
  else
    line1=$(link_name "$(wrap_name 📁 "$folder" "$max")" "")
    [[ -n $branch ]] && line1+=$'\n'$(link_name "$(wrap_name 🌿 "$branch" "$max")" "$branch_url")
  fi
fi

five_left="" week_left=""
[[ $five != "-" ]] && five_left=$(until_reset "$five_reset")
[[ $week != "-" ]] && week_left=$(until_reset "$week_reset")

# Line 2: context, model + effort, limits, account (least important last: cut first if too wide)
line2="$(show ctx "$ctx_pct" "$ctx_colour")${sep}${model}${sep}$(show 5h "$five" "$five_colour" "$five_mark")${five_left}${sep}$(show 7d "$week" "$week_colour" "$week_mark")${week_left}${sep}${account}"

[[ -n $line1 ]] && printf '%s\n' "$line1"
printf '%s\n' "$line2"
