all:	orangepi_power.eps orangepi_temperature.eps orangepi_frequency.eps \
	orangepi_combined.eps orangepi_compact.pdf

###

orangepi_compact.pdf:	orangepi_compact.eps
	epstopdf orangepi_compact.eps

orangepi_compact.eps:	orangepi_compact.jgr
	jgraph < orangepi_compact.jgr > orangepi_compact.eps

###

orangepi_combined.eps:	orangepi_combined.jgr
	jgraph < orangepi_combined.jgr > orangepi_combined.eps

orangepi_power.eps:	orangepi_power.jgr
	jgraph < orangepi_power.jgr > orangepi_power.eps

orangepi_temperature.eps:	orangepi_temperature.jgr
	jgraph < orangepi_temperature.jgr > orangepi_temperature.eps

orangepi_frequency.eps:	orangepi_frequency.jgr
	jgraph < orangepi_frequency.jgr > orangepi_frequency.eps

clean:	
	rm -f *~ *.eps *.pdf

