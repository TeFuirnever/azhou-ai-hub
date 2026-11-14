#!/usr/bin/env bash
# Append a well-formed row to a show-me-your-work decision log (TSV).
# Usage: log.sh <logfile> <phase> <decision> <why> <evidence> <result>
set -euo pipefail

if [ "$#" -ne 6 ]; then
	printf 'usage: log.sh <logfile> <phase> <decision> <why> <evidence> <result>\n' >&2
	exit 1
fi

logfile="$1"
shift

logdir="$(dirname "$logfile")"
if [ -n "$logdir" ] && [ "$logdir" != "." ] && [ ! -d "$logdir" ]; then
	mkdir -p "$logdir"
fi

# Use `>>` here, never `>`. A network mount can fail this test for a log
# that exists. Then the cost is one stray header line, not the rows.
if [ ! -s "$logfile" ]; then
	printf 'ts\tphase\tdecision\twhy\tevidence\tresult\n' >> "$logfile"
fi

ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
# Strip tabs/newlines/CR so cells stay on one line, and prefix any cell
# whose first char a spreadsheet would parse as a formula (=, +, -, @)
# with a single quote. The skill expects this log to be read in
# spreadsheets, so attacker-controlled evidence (PR titles, filenames,
# generated text) must not become formula execution when a reviewer
# opens the file.
clean() {
	local v
	v=$(printf '%s' "$1" | tr '\t\n\r' '   ')
	case "$v" in
		=*|+*|-*|@*|\"*) printf "'%s" "$v" ;;
		*) printf '%s' "$v" ;;
	esac
}
# Build the row before the append so the append is one write. A shell printf goes
# through stdio, which hands a row longer than its buffer to the kernel in pieces
# that parallel writers interleave, and the TSV no longer parses.
printf -v row '%s\t%s\t%s\t%s\t%s\t%s\n' \
	"$ts" "$(clean "$1")" "$(clean "$2")" "$(clean "$3")" "$(clean "$4")" "$(clean "$5")"
# perl runs once before it sees the row, so a perl that is missing, shimmed or
# broken by PERL5OPT cannot take the row with it. binmode drops the :utf8 layer
# PERL_UNICODE adds: syswrite refuses that on STDOUT, and on STDIN it would
# decode the row and corrupt non-ASCII bytes. A short write sets no $!, so it
# reports the byte counts instead.
if [ "$(perl -e 'print "ok"' 2>/dev/null </dev/null)" = ok ]; then
	printf '%s' "$row" |
		perl -e 'binmode STDIN; binmode STDOUT; local $/; $_ = <STDIN>;
			my $n = syswrite(STDOUT, $_) // die "log.sh: $!\n";
			$n == length or die "log.sh: short write, appended $n of ", length, " bytes of the row\n"' \
			>> "$logfile"
else
	printf '%s' "$row" >> "$logfile"
fi
