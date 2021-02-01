## General considerations
As my objective is to construct a graph of a sample design, there is no need to distinguish high or low output drive strength.
All that is needed is the type of cell to correctly represent the structure of the design.

## Cells
All these info are extracted from the [OSU website](https://vlsiarch.ecen.okstate.edu/flows/stdcell_datasheet/OSUFreePDK45/).

### AND2X1 & AND2X2
`Y=(A&B)`

### AOI21X1
`Y=!((A&B)|C)`
"And, Or, Inverted".

[More info](http://www.vlsitechnology.org/html/cells/vsclib013/aoi21.html)

### AOI22X1
`Y=!((C&D)|(A&B))`

### BUFX2 & BUFX4
`Y=A`

### CLKBUF1 & CLKBUF2 & CLKBUF3
`Y=A`, but for the clock.

### DFFNEGX1
```
FLIPFLOP{
  DATA=D
  CLOCK=!CLK
  Q=DS0000
  QN=P0000
}
Q=DS0000
```

### DFFPOSX1
```
FLIPFLOP{
  DATA=D
  CLOCK=CLK
  Q=DS0000
  QN=P0000
}
Q=DS0000
```

### DFFSR
```
FLIPFLOP{
  DATA=D
  CLOCK=CLK
  PRESET=!S
  CLEAR=!R
  Q=P0002
  QN=P0003
}
Q=P0002
```

### FAX1
```
YC=((A&B)|(B&C)|(C&A))
YS=(A^B^C)
```

### HAX1
```
YS=(A^B)
YC=(A&B)
```

### INVX1 & INVX2 & INVX4 & INVX8
`Y=!A`

### LATCH
```
Latch{
  DATA=D
  CLOCK=CLK
  Q=DS0000
  QN=P0000
}
Q=DS0000
```
Which is the same function as `DFFPOSX1`, but not the same power.

### MUX2X1
`Y=!(S?(A:B))`

### NAND2X1
`Y=!(A&B)`

### NAND3X1
`Y=!(A&B&C)`

### NOR2X1
`Y=!(A|B)`

### NOR3X1
`Y=!(A|B|C)`

### OAI21X1
`Y=!((A|B)&C)`
"Or (2), And(1), Inverted".

### OAI22X1
`Y=!((C|D)&(A|B))`

### OR2X1 & OR2X2
`Y=(A|B)`

### TBUFX1 & TBUFX2
`Y=(EN?!A:'BZ)`

### XNOR2X1
`Y=!(A^B)`

### XOR2X1
`Y=(A^B)`