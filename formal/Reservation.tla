------------------------- MODULE Reservation -------------------------
EXTENDS Naturals, FiniteSets, TLC

CONSTANTS Orders, Capacity
ASSUME /\ IsFiniteSet(Orders) /\ Orders # {}
       /\ Capacity \in Nat \ {0}

VARIABLES phase, seen, amount, reserved, version
vars == <<phase, seen, amount, reserved, version>>

RECURSIVE Total(_)
Total(S) == IF S = {} THEN 0
            ELSE LET o == CHOOSE x \in S : TRUE
                 IN reserved[o] + Total(S \ {o})

Init == /\ phase = [o \in Orders |-> "idle"]
        /\ seen = [o \in Orders |-> 0]
        /\ amount = [o \in Orders |-> 0]
        /\ reserved = [o \in Orders |-> 0]
        /\ version = 0

Begin(o, n) == /\ phase[o] = "idle"
               /\ n \in 1..Capacity
               /\ phase' = [phase EXCEPT ![o] = "pending"]
               /\ seen' = [seen EXCEPT ![o] = version]
               /\ amount' = [amount EXCEPT ![o] = n]
               /\ UNCHANGED <<reserved, version>>

Commit(o) == /\ phase[o] = "pending"
             /\ seen[o] = version
             /\ Total(Orders) + amount[o] <= Capacity
             /\ phase' = [phase EXCEPT ![o] = "held"]
             /\ reserved' = [reserved EXCEPT ![o] = amount[o]]
             /\ version' = version + 1
             /\ UNCHANGED <<seen, amount>>

Reject(o) == /\ phase[o] = "pending"
             /\ \/ seen[o] # version
                \/ Total(Orders) + amount[o] > Capacity
             /\ phase' = [phase EXCEPT ![o] = "rejected"]
             /\ UNCHANGED <<seen, amount, reserved, version>>

Release(o) == /\ phase[o] = "held"
              /\ phase' = [phase EXCEPT ![o] = "released"]
              /\ reserved' = [reserved EXCEPT ![o] = 0]
              /\ version' = version + 1
              /\ UNCHANGED <<seen, amount>>

Next == \E o \in Orders :
          \/ \E n \in 1..Capacity : Begin(o, n)
          \/ Commit(o)
          \/ Reject(o)
          \/ Release(o)

Spec == Init /\ [][Next]_vars

TypeOK == /\ phase \in [Orders -> {"idle", "pending", "held", "rejected", "released"}]
          /\ seen \in [Orders -> Nat]
          /\ amount \in [Orders -> 0..Capacity]
          /\ reserved \in [Orders -> 0..Capacity]
          /\ version \in Nat

NoOvercommit == Total(Orders) <= Capacity
HeldMatchesReservation == \A o \in Orders :
    IF phase[o] = "held" THEN reserved[o] = amount[o] /\ amount[o] > 0
    ELSE reserved[o] = 0
=======================================================================
