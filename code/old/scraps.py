

l = 4294032
t = 2893435
r = 4592459
b = 2678180

ix = 0
iy = 0
count = 1

with open('data/zensus.csv', 'r') as f:
        for line in f:
            print line
            x = int(line[17:24]) #slicing is faster than spliting on ;
            y = int(line[25:32])
            #val = int(line[33:])
            #print x, ',',y,'',val
            if x in xrange(l,r) and y in xrange(b,t):
                #print line
                count += 1
           #     ix+=1
           #     iy+=1
                if not count % 1000:
                    print count