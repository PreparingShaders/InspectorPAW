f = open("templates/nutrition.html", "r", encoding="utf-8")
c = f.read()
f.close()
old = """          .icon-nova   { background: rgba(192,132,252,0.15); }
    </style>"""
new = """          .icon-nova   { background: rgba(192,132,252,0.15); }
          .meal-type-btn.active {
              background-color: rgba(168, 85, 247, 0.3);
              color: #fff;
              text-shadow: 0 0 8px rgba(192, 132, 252, 0.6);
              box-shadow: 0 0 12px rgba(168, 85, 247, 0.3);
          }
          #meal-type-selector.error {
              border-color: #EF4444;
              box-shadow: 0 0 10px rgba(239, 68, 68, 0.4);
          }
    </style>"""
c = c.replace(old, new)
f = open("templates/nutrition.html", "w", encoding="utf-8")
f.write(c)
f.close()
print("done")
