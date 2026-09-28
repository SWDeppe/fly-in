# Algorithm description

For this project i choosed the **CBS*** algorithm it is composed if a 2 layered algo a **top** and **low** level one.

## Low level

for the low level i chossed a a* with an exacte heuristic precalculated with a djicstra algorithm runed backwards with a frontier that needs to be completely used.

#### A* description

The a* algorithme will start on the start hub and from the neighbours found calculate a score the score consiste of h(estimated heuristic that mean the estimated steps needed to arricve to end) + t(current time).
By doing so the a* algorithm goes into a correct direction and dosent need to explore the whole map to get a nearly perfect path.
**disclaimer**: The a* algorithm is heigly dependent on its heuristic in the actual case i run a* a lot of times so i estimated the cost of runing once a djikstra to create a proper heuristic useful but if it would be s position based heuristic i dosent garenty a good a* algo simpley cause the position is not very significative untile one connection is one single step but some connections have a h = 3 and some h = 1 but are equal so a* could do a lot of mistakes on not very well writen maps !

## Top level

The top level algo is simply there to verify the paths runed threw the a* algo to find a conflict a conflict simply consiste of too many drones on a hub/connection, if a conflict is found it builds a conflict tree where every conflict generates 2 new nodes each node will get its paths and a score we go to the nodes having the best scores. To generate the new paths without the same conflict we feed the a* a constraint that is juste giving somply at simulation time t drone n cannot go at hub/connection p.

### CBS variants

After the years of research in the it world there where a lot of variants of this algorithm that can performe way better than this one on spescifique cases for exemple if the most hubs/connection would accept more than 1 drone we could use ECBS that would groupe some drones together (i made the choice of normal CBS cause there was not even one map that hase more than half of the hubs accepting more than 1 drone what means that this architecture choice would juste evercomplexify the algo for a veri minimal optimisation) and other variants that i dosen't took in consideration cause if time constraints !