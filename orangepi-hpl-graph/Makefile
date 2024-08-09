all:	orangepi_hpl.pdf

###

orangepi_hpl.pdf:	orangepi_hpl.eps
	epstopdf orangepi_hpl.eps

orangepi_hpl.eps:	orangepi_hpl.jgr
	jgraph < orangepi_hpl.jgr > orangepi_hpl.eps

###

clean:	
	rm -f *~ *.eps *.pdf

