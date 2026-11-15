from manim import *

class RagyTeamAnimation(Scene):
    def construct(self):
        # Setup
        self.camera.background_color = "#0A0A0A"
        
        # Team Members
        gm = Text("الريس منصور (GM)", color=BLUE, font_size=36)
        dev = Text("ماهر (Dev)", color=GREEN, font_size=36)
        qa = Text("فاروق (QA)", color=RED, font_size=36)
        res = Text("لبيب (Research)", color=YELLOW, font_size=36)
        
        # Layout
        gm.shift(UP * 2)
        dev.shift(LEFT * 3 + DOWN * 1)
        qa.shift(RIGHT * 3 + DOWN * 1)
        res.shift(DOWN * 2.5)
        
        # Group
        team = VGroup(gm, dev, qa, res)
        
        # Animation
        self.play(Write(gm), run_time=1)
        self.wait(0.5)
        self.play(Write(dev), Write(qa), Write(res), run_time=1.5)
        self.wait(1)
        
        # Connecting lines
        l1 = Line(gm.get_bottom(), dev.get_top(), color=WHITE)
        l2 = Line(gm.get_bottom(), qa.get_top(), color=WHITE)
        l3 = Line(gm.get_bottom(), res.get_top(), color=WHITE)
        
        self.play(Create(l1), Create(l2), Create(l3), run_time=1)
        self.wait(2)
        
        # Final Text
        final_text = Text("RAGY Team: Active & Integrated", color=BLUE, font_size=48)
        self.play(FadeOut(team), FadeOut(l1), FadeOut(l2), FadeOut(l3))
        self.play(Write(final_text))
        self.wait(3)
