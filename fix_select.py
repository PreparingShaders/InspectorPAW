f = open("templates/nutrition.html", "r", encoding="utf-8")
c = f.read()
f.close()
c = c.replace(
    "w-full bg-white/5 border border-white/10 rounded-xl p-3 text-white text-center transition-all duration-300 focus:ring-2 focus:ring-purple-500 focus:border-purple-500",
    "hidden",
)
f = open("templates/nutrition.html", "w", encoding="utf-8")
f.write(c)
f.close()
print("done")
