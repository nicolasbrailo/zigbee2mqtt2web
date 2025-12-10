# timestamp
(try (.["_SOURCE_REALTIME_TIMESTAMP"] | tonumber / 1000000 | strftime("%m-%d %H:%M:%S")) catch "N/A") as $ts |

# severity mapping
(try (["EMRG","ALRT","CRIT","ERRR","WARN","NOTI","INFO","DEBG"][(.PRIORITY|tonumber)]) catch (try .PRIORITY catch "N/A")) as $sev |

# unit name without .service
(try (.["_SYSTEMD_UNIT"] // "Unit?") catch "Unit?" | sub("\\.service$"; "")) as $unit |

(try (.["LOGGER"] // "?") catch "?") as $logger |

# source file relative to base path
((try (.CODE_FILE // "-") catch "-" | sub("^/home/batman/src/baticasa2/"; "") | sub("^.*/\\.venv/lib/[^/]+/site-packages/"; "")) + (try ((":" + .CODE_LINE // "") | tostring) catch "")) as $src |

# ANSI color for errors (0-3)
(if (try (.PRIORITY|tonumber) catch 99) <= 3 then "\u001b[31m" else "" end) as $color |

# final output
($color + $ts + " " + $unit + "." + $logger + " " + $sev + " " + $src + " " + (try (if (.MESSAGE | type) == "array" then (.MESSAGE | implode) else (.MESSAGE // "") end) catch "") + "\u001b[0m")
