Without the lease check, a concurrent push silently overwrites the tip; a naive retry loop would mask it.
