

l = 4353251
t = 2841928
r = 4517293
b = 2710959

ix = 0
iy = 0
count = 1

with open('data/zensus.csv', 'r') as f:
    with open('data/output.txt', 'w') as output:
        output.write(f.read())
        f.next() #kskip header line
        for line in f:
            x = int(line[17:24]) #slicing is faster than spliting on ;
            y = int(line[25:32])
            val = int(line[33:])
            #print x, ',',y,'',val
            if x in xrange(l,r) and y in xrange(b,t):
                if int(val) > 0:
                    #print line
                    output.write(line)
                    count += 1

           #     ix+=1
           #     iy+=1
                if not count % 1000:
                    print count