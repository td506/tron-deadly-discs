;; ======================================================================== ;;
;;  TRON Deadly Discs mods                                                   ;;
;;                                                                           ;;
;;  Each mod is an IF block that re-ORGs over retail words.  The MOD_*      ;;
;;  switches come from options.asm, which tools/tron_build.py writes into   ;;
;;  build/ for every build.  With every switch at 0 the output is           ;;
;;  byte-identical to the retail cartridge (CRC32 CA447BBD).                ;;
;;                                                                           ;;
;;  Mods marked "(Hack.cfg)" reproduce the jzIntv [macro] patches from      ;;
;;  "Tron Deadly Discs (Hack).cfg".                                         ;;
;; ======================================================================== ;;

        INCLUDE "options.asm"

;; ------------------------------------------------------------------------ ;;
;;  Colors (Hack.cfg)                                                       ;;
;; ------------------------------------------------------------------------ ;;
        IF MOD_COLORS
        ORG     $50F9
        DECLE   $0055           ; Tron: light blue (retail $0042 red)
        ORG     $5109
        DECLE   $0081           ; Tron's disc: blue (retail $0086 yellow)
        ORG     $5C2A
        DECLE   $0054           ; Warriors: pink (retail $0055 light blue)
        ORG     $5DB4
        DECLE   $0080           ; Enemy discs: black (retail $0081 blue)
        ENDI

;; ------------------------------------------------------------------------ ;;
;;  Start with a big score (Hack.cfg)                                       ;;
;;  Game init at $5B43 loads R4=$10, stores it to $0119, then clears        ;;
;;  $012D/$0317/$0318.  Reordered so $10 also lands in score high word      ;;
;;  $0317 before the CLRR.  Score display shows 0, but Guards appear at     ;;
;;  once because the game thinks you are past their threshold.              ;;
;; ------------------------------------------------------------------------ ;;
        IF MOD_START_SCORE
        ORG     $5B47
        MVO     R4,     $0317   ; score high word = $10
        CLRR    R4
        MVO     R4,     $012D
        ENDI

;; ------------------------------------------------------------------------ ;;
;;  First point-value tier = 10,000 (Hack.cfg)                              ;;
;; ------------------------------------------------------------------------ ;;
        IF MOD_POINT_TIER
        ORG     $583C
        DECLE   1000            ; retail 5
        ENDI

;; ------------------------------------------------------------------------ ;;
;;  Jump straight to the highest point tier (Hack.cfg, commented out there) ;;
;; ------------------------------------------------------------------------ ;;
        IF MOD_TOP_TIER
        ORG     $5F32
        DECLE   $0204           ; BNEQ L_5F60 -> BEQ L_5F60
        ENDI

;; ------------------------------------------------------------------------ ;;
;;  Swap score high/low word stores (Hack.cfg, commented out there)         ;;
;;  Score runs into the 9-figure range quickly.                             ;;
;; ------------------------------------------------------------------------ ;;
        IF MOD_CROSS_SCORE
        ORG     $5F3D
        MVO     R0,     $0317   ; retail: MVO R0, $0318
        MVO     R1,     $0318   ; retail: MVO R1, $0317
        ENDI

;; ------------------------------------------------------------------------ ;;
;;  Recognizer eye: remove shield graphic (Hack.cfg)                        ;;
;; ------------------------------------------------------------------------ ;;
        IF MOD_RECOG_NO_SHIELD
        ORG     $531D
        DECLE   0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
        ENDI

;; ------------------------------------------------------------------------ ;;
;;  Recognizer eye: bigger, easier to hit (Hack.cfg)                        ;;
;; ------------------------------------------------------------------------ ;;
        IF MOD_RECOG_BIG_EYE
;;  Words $532F/$5337/$533F/$5347 (the eye's own rows) are left as-is.     ;;
        ORG     $532D
        DECLE   $7E, $FF
        ORG     $5330
        DECLE   $FF, $FF, $FF
        ORG     $5335
        DECLE   $7E, $FF
        ORG     $5338
        DECLE   $FF, $FF, $FF
        ORG     $533D
        DECLE   $7E, $FF
        ORG     $5340
        DECLE   $FF, $FF, $FF
        ORG     $5345
        DECLE   $7E, $FF
        ORG     $5348
        DECLE   $FF, $FF, $FF
        ENDI

;; ------------------------------------------------------------------------ ;;
;;  "GAME OVER" -> "DEREZZED!" (Hack.cfg)                                   ;;
;; ------------------------------------------------------------------------ ;;
        IF MOD_DEREZZED
        ORG     $5877
        STRING  "DEREZZED!"     ; same 9 words, existing $0000 terminator kept
        ENDI

;; ------------------------------------------------------------------------ ;;
;;  tron.bin variant: the branch at $56EB in L_56CE (hit/collision test,    ;;
;;  result in carry) goes to CLRC instead of SETC when the object's type    ;;
;;  field (R1+5) is not 4.  Unknown whether this is a bad dump or a hack.   ;;
;; ------------------------------------------------------------------------ ;;
        IF MOD_TRONBIN_BRANCH
        ORG     $56EB
        BNEQ    HitTest_No
        ENDI
